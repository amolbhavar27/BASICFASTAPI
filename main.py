from fastapi import FastAPI, Request , HTTPException ,status , Depends

from contextlib import asynccontextmanager
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

#from fastapi.responses import HTMLResponse # for only html file routing but now we have jinjatemplet hence we dont required that
# from fastapi.responses import JSONResponse  # not require for asyn method
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPExeception

from sqlalchemy import select
from sqlalchemy.ext.asyncio import  AsyncSession
from sqlalchemy.orm import selectinload


from typing import Annotated
import models
from database import Base ,engine,get_db
#  Base.metadata.create_all(bind=engine) # these is sychronous method to bind engine

from routers import posts,users


@asynccontextmanager
async def lifespan(_app : FastAPI ):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

    await engine.dispose()


app=FastAPI(lifespan=lifespan)

app.mount("/media", StaticFiles(directory="media"),name="media" )
app.mount("/static", StaticFiles(directory="static"), name="static")

templates= Jinja2Templates(directory="templates")


app.include_router(users.router,prefix="/api/users", tags=["users"])
app.include_router(posts.router,prefix="/api/posts", tags=["posts"])


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts",include_in_schema=False, name="posts")
async def home(request: Request,db:Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.Post).options(selectinload(models.Post.author)).order_by(models.Post.date_posted.desc()))
    posts=result.scalars().all()
    return templates.TemplateResponse(request,"home.html",{"posts":posts,"title":"home"})

@app.get("/posts/{post_id}", include_in_schema=False)
async def post_page(request : Request, post_id : int ,db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post= result.scalars().first()
    if post:
        title = post.title[:50]
        return templates.TemplateResponse(request,"post.html",{"post":post,"title":title})
    raise HTTPException(status_code= status.HTTP_404_NOT_FOUND,detail= "post not found")


@app.get("/api/users/{user_id}/posts",include_in_schema=False, name="user_posts")
async def get_user_posts(request : Request, user_id: int, db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id==user_id))
    user= result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    
    result =await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id==user_id))
    posts=result.scalars().all()
    return templates.TemplateResponse(request,"user_posts.html",{"posts":posts,"user":user,"title":f"{user.username} 's posts"})


@app.exception_handler(StarletteHTTPExeception)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPExeception):

    if request.url.path.startswith("/api"):
        return await http_exception_handler(request,exception)
    
    message = (
        exception.detail
        if exception.detail
        else "an error occurred. please check your request and try again "
    )
    return templates.TemplateResponse(
        request,"error.html", 
        {
            "status_code":exception.status_code,
            "title":exception.status_code,
            "message":message

        },
        status_code=exception.status_code
    )
    
@app.exception_handler(RequestValidationError)
async def general_validationError(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)
    
    return templates.TemplateResponse(
        request, "error.html",
        {
            "status_code":status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title":status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message":"invalid request .pls check your input and try again "
        
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT        
    )




