from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload
from typing import List

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/api/stock", tags=["stock"])


# ---------- Locations ----------
@router.get("/locations", response_model=List[schemas.StockLocationOut])
def list_locations(request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    return (
        db.query(models.StockLocation)
        .filter(models.StockLocation.company_id == company_id)
        .order_by(models.StockLocation.created_at)
        .all()
    )


@router.post("/locations", response_model=schemas.StockLocationOut)
def create_location(payload: schemas.StockLocationCreate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)

    # Case-insensitive duplicate check - "PG College Godown" and "pg college
    # godown" are the same place typed twice, most likely by accident (a
    # double-tap, or submitting twice not realizing the first one worked).
    existing = (
        db.query(models.StockLocation)
        .filter(models.StockLocation.company_id == company_id)
        .all()
    )
    if any(loc.name.strip().lower() == payload.name.strip().lower() for loc in existing):
        raise HTTPException(409, f'A location named "{payload.name}" already exists')

    location = models.StockLocation(company_id=company_id, name=payload.name)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.delete("/locations/{location_id}")
def delete_location(location_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    location = db.query(models.StockLocation).filter(
        models.StockLocation.id == location_id, models.StockLocation.company_id == company_id
    ).first()
    if not location:
        raise HTTPException(404, "Location not found")

    # Removing a location also removes whatever stock records point at it -
    # there's no meaningful state for "10 bags at a place that doesn't
    # exist anymore". The item itself and its stock at every OTHER location
    # is untouched.
    db.query(models.ItemStock).filter(models.ItemStock.location_id == location_id).delete(synchronize_session=False)
    db.delete(location)
    db.commit()
    return {"ok": True}


# ---------- Items ----------
@router.get("/items", response_model=List[schemas.ItemOut])
def list_items(request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    items = (
        db.query(models.Item)
        .options(selectinload(models.Item.stock_entries).selectinload(models.ItemStock.location))
        .filter(models.Item.company_id == company_id)
        .order_by(models.Item.name)
        .all()
    )
    return [_to_out(i) for i in items]


@router.post("/items", response_model=schemas.ItemOut)
def create_item(payload: schemas.ItemCreate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    item = models.Item(
        company_id=company_id,
        name=payload.name,
        unit=payload.unit,
        reorder_threshold=payload.reorder_threshold,
        created_by=auth.get_current_username(request),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.put("/items/{item_id}", response_model=schemas.ItemOut)
def update_item(item_id: str, payload: schemas.ItemUpdate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.company_id == company_id).first()
    if not item:
        raise HTTPException(404, "Item not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.delete("/items/{item_id}")
def delete_item(item_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.company_id == company_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.put("/items/{item_id}/set", response_model=schemas.ItemOut)
def set_stock(item_id: str, payload: schemas.StockSetRequest, request: Request, db: Session = Depends(get_db)):
    """
    Sets the quantity of one item at one location directly - matching the
    actual workflow described: someone counts what's physically there and
    types in the real number, rather than logging individual additions and
    subtractions. Creates the (item, location) row the first time a
    quantity is set for that combination.
    """
    company_id = auth.get_current_company_id(request)
    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.company_id == company_id).first()
    if not item:
        raise HTTPException(404, "Item not found")

    location = db.query(models.StockLocation).filter(
        models.StockLocation.id == payload.location_id, models.StockLocation.company_id == company_id
    ).first()
    if not location:
        raise HTTPException(404, "Location not found")

    entry = db.query(models.ItemStock).filter(
        models.ItemStock.item_id == item_id, models.ItemStock.location_id == payload.location_id
    ).first()
    if not entry:
        entry = models.ItemStock(item_id=item_id, location_id=payload.location_id, quantity=payload.quantity)
        db.add(entry)
    else:
        entry.quantity = payload.quantity

    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.put("/items/{item_id}/transfer", response_model=schemas.ItemOut)
def transfer_stock(item_id: str, payload: schemas.StockTransferRequest, request: Request, db: Session = Depends(get_db)):
    """
    Moves a quantity of one item from one location to another in a single
    action - decreases the source, increases the destination, both at
    once. This is what actually distinguishes a transfer from just editing
    two numbers by hand: the two sides can never end up out of sync with
    each other (e.g. someone updating the source but forgetting the
    destination), since it's one atomic operation instead of two
    independent edits.
    """
    company_id = auth.get_current_company_id(request)
    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.company_id == company_id).first()
    if not item:
        raise HTTPException(404, "Item not found")

    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(422, "Source and destination can't be the same place")

    from_location = db.query(models.StockLocation).filter(
        models.StockLocation.id == payload.from_location_id, models.StockLocation.company_id == company_id
    ).first()
    to_location = db.query(models.StockLocation).filter(
        models.StockLocation.id == payload.to_location_id, models.StockLocation.company_id == company_id
    ).first()
    if not from_location or not to_location:
        raise HTTPException(404, "Location not found")

    from_entry = db.query(models.ItemStock).filter(
        models.ItemStock.item_id == item_id, models.ItemStock.location_id == payload.from_location_id
    ).first()
    available = from_entry.quantity if from_entry else 0
    if payload.quantity > available:
        raise HTTPException(
            422, f"Only {available} available at {from_location.name} - can't transfer {payload.quantity}"
        )

    from_entry.quantity -= payload.quantity

    to_entry = db.query(models.ItemStock).filter(
        models.ItemStock.item_id == item_id, models.ItemStock.location_id == payload.to_location_id
    ).first()
    if not to_entry:
        to_entry = models.ItemStock(item_id=item_id, location_id=payload.to_location_id, quantity=payload.quantity)
        db.add(to_entry)
    else:
        to_entry.quantity += payload.quantity

    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.get("/low-stock", response_model=List[schemas.ItemOut])
def low_stock_items(request: Request, db: Session = Depends(get_db)):
    """Separate, lightweight endpoint for the Dashboard rather than folding
    this into the already-heavy summary endpoint - keeps that one from
    growing any further after it was the exact endpoint that once crashed
    from doing too much at once."""
    company_id = auth.get_current_company_id(request)
    items = (
        db.query(models.Item)
        .options(selectinload(models.Item.stock_entries))
        .filter(models.Item.company_id == company_id, models.Item.reorder_threshold.isnot(None))
        .all()
    )
    return [_to_out(i) for i in items if i.is_low_stock]


def _to_out(item: models.Item) -> schemas.ItemOut:
    return schemas.ItemOut(
        id=item.id,
        name=item.name,
        unit=item.unit,
        reorder_threshold=item.reorder_threshold,
        created_at=item.created_at,
        created_by=item.created_by,
        stock_by_location=[
            schemas.ItemStockEntry(
                location_id=s.location_id,
                location_name=s.location.name if s.location else "Unknown",
                quantity=s.quantity,
            )
            for s in item.stock_entries
        ],
        total_quantity=item.total_quantity,
        is_low_stock=item.is_low_stock,
    )
