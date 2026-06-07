from fastapi import APIRouter

from echomemory_backend.api.v1.endpoints import album, auth, collection, comment, dictionary, music, play_history, playlist, users

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(dictionary.router)
router.include_router(music.router)
router.include_router(play_history.router)
router.include_router(playlist.router)
router.include_router(album.router)
router.include_router(collection.router)
router.include_router(comment.router)
