from fastapi import APIRouter

from echomemory_backend.api.v1.endpoints import auth, dictionary, music, users

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(dictionary.router)
router.include_router(music.router)
