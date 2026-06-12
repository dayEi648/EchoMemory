"""API v1 总路由模块，负责聚合并注册所有 v1 版本的子路由。"""

from fastapi import APIRouter

from echomemory_backend.api.v1.endpoints import album, auth, carousel, collection, comment, dictionary, music, play_history, playlist, space_post, users

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
router.include_router(space_post.router)
router.include_router(carousel.router)
