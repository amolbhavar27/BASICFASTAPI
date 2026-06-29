from fastapi import FastAPI, Request , HTTPException ,status , Depends
from fastapi.responses import HTMLResponse # for only html file routing but now we have jinjatemplet hence we dont required that
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPExeception

from sqlalchemy import select
from sqlalchemy.orm import  Session

from typing import Annotated
import models
from database import Base ,engine,get_db
from schemas import PostCreate,PostResponse, UserCreate,UserResponse

Base.metadata.create_all(bind=engine)

app=FastAPI()

app.mount("/media", StaticFiles(directory="media"),name="media" )
app.mount("/static", StaticFiles(directory="static"), name="static")

templates= Jinja2Templates(directory="templates")

@app.get("/post/{post_id}", include_in_schema=False,response_model=PostResponse)
def post_page(request : Request, post_id : int ):
    for post in posts:
        title=post["title"][:12]
        if post.get("id")==post_id:
            return templates.TemplateResponse(request,"post.html",{"post":post, "title":title})

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="post not found")

@app.get("/",include_in_schema=False,name="home",response_model=list[PostResponse])
@app.get("/post",name="posts",response_model=list[PostResponse])
def home(request:Request):
    return templates.TemplateResponse(request,"home.html",{"posts":posts,"title":"home",})


@app.get("/api/post/{post_id}")
def get_post(post_id: int):
    for post in posts:
        if post.get("id") == post_id :
            return post
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")


@app.exception_handler(StarletteHTTPExeception)
def general_http_exception_handler(request: Request, exception: StarletteHTTPExeception):
    message = (
        exception.detail
        if exception.detail
        else "an error occurred. please check your request and try again "
    )

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail":message},
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
def general_validationError(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()}
        )
    return templates.TemplateResponse(
        request, "error.html",
        {
            "status_code":status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title":status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message":"invalid request .pls check your input and try again "
        
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT        
    )

@app.post("/api/posts",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate):
    new_id = max(p["id"]  for p in posts) + 1 if posts else 1
    new_post= {
        "id" : new_id,
        "title":post.title,
        "author" : post.author,
        "content": post.content,
        "date_posted" : "28 june 2026"
    }
    posts.append(new_post)
    return new_post

@app.post("/api/users",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate,db: Annotated[Session,Depends(get_db)]):
    return db.execute(
        select(models.User).where(models.user.username == user.username)
    )
