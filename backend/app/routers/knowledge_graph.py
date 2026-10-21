from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.knowledge_graph import knowledge_graph
from app.models import User

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


@router.get("")
def get_graph(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return knowledge_graph(db)
