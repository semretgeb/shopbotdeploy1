from fastapi import APIRouter, HTTPException, Query, Response

from app.services.images import ImageNotFound, get_image

router = APIRouter(prefix="/api")


@router.get("/img/{file_id}", include_in_schema=False)
async def proxy_image(file_id: str, w: int = Query(default=640)) -> Response:
    # No initData here on purpose: <img> tags can't send headers. file_ids are long random
    # strings, so the URL is unguessable; the response is public product imagery anyway.
    try:
        data = await get_image(file_id, w)
    except ImageNotFound:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(
        content=data,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
