import os, uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Property, Rule, Movement

from ..deps import get_current_user
from ..config import settings
from ..services.movements import read_movements_excel, classify

router = APIRouter(prefix="/movements", tags=["movements"])

@router.post("/upload")
async def upload_movements(property_id: int | None = None,
                           f: UploadFile = File(...),
                           session: Session = Depends(get_session),
                           user=Depends(get_current_user)):
    # guarda archivo
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in [".xls", ".xlsx"]:
        raise HTTPException(400, "Solo .xls/.xlsx")
    stored = os.path.join(settings.app_data_dir, f"{uuid.uuid4()}{ext}")
    with open(stored, "wb") as out:
        out.write(await f.read())

    mf = MovementFile(property_id=property_id, original_name=f.filename, stored_path=stored)
    session.add(mf); session.commit(); session.refresh(mf)

    df = read_movements_excel(stored)
    # guarda RAW
    raws = [MovementRaw(file_id=mf.id,
                        fecha=r["Fecha"].date() if hasattr(r["Fecha"],"date") else r["Fecha"],
                        concepto=str(r["Concepto"]),
                        importe=float(r["Importe"]),
                        saldo=float(r["Saldo"]) if r["Saldo"]==r["Saldo"] else None)
            for _, r in df.iterrows()]
    session.add_all(raws); session.commit()

    # clasificación si se pasó property_id
    classified_count = 0
    if property_id:
        reglas = session.exec(select(Rule).where(Rule.property_id == property_id)).all()
        reglas_dict = [r.dict() for r in reglas]
        cdf = classify(df, reglas_dict, property_id)
        rows = [MovementClassified(property_id=property_id,
                                   fecha=r["Fecha"],
                                   concepto=r["Concepto"],
                                   importe=r["Importe"],
                                   categoria=r["categoria"],
                                   subcuenta=r.get("subcuenta"),
                                   inquilino=r.get("inquilino")) for _, r in cdf.iterrows()]
        session.add_all(rows); session.commit()
        classified_count = len(rows)

    return {"file_id": mf.id, "raw_rows": len(raws), "classified_rows": classified_count}

@router.get("")
def list_movements(property_id: int,
                   session: Session = Depends(get_session),
                   user=Depends(get_current_user)):
    q = select(MovementClassified).where(MovementClassified.property_id == property_id)
    return session.exec(q).all()
