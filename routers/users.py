
from datetime import timedelta

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException,status
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
  
from fastapi.security import OAuth2PasswordRequestForm

from auth import create_access_token,verity_access_token,verity_password,hash_password,oauth2_scheme
from config import settings

import models 
from database import get_db
from schemas import UserCreate,UserPrivate,UserPublic, UserUpdate, PostResponse ,Token


router = APIRouter()


@router.post("/",response_model= UserPrivate,status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.User).where(func.lower(models.User.username) == user.username.lower()))
    existing_user= result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username already exists")
    
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == user.email.lower()))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email already exists")
    
    new_user =models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash= hash_password(user.password)
        )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/token", response_model=Token) 
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm,Depends()],
    db : Annotated[AsyncSession,Depends(get_db)]
):
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) ==form_data.username.lower()
        )
    )
    user = result.scalars().first()
    if not user or not verity_password(form_data.password,user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="incorrect email or password",headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data = {"sub": str(user.id)},
        expire_delta=access_token_expires,
    )
    return Token(access_token= access_token,token_type="bearer")
    

@router.get("/me",response_model=UserPrivate)
async def get_current_user(
    token : Annotated[str ,Depends(oauth2_scheme)],
    db : Annotated[AsyncSession,Depends(get_db)]

):
    user_id= verity_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token",headers={"WWW-Authenticate": "Bearer"})
    
    try:
        user_id_int = int(user_id)
    except (TypeError,ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token",headers={"WWW-Authenticate": "Bearer"}) 
    
    result = await db.execute(select(models.User).where(models.User.id == user_id_int))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="user not found ",headers={"WWW-Authenticate": "Bearer"})
    
    return user 


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: int, db:Annotated[AsyncSession, Depends(get_db)]):
    result =await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

@router.patch("/{user_id}",response_model=UserPrivate)
async def update_user(user_id: int,  user_update:UserUpdate, db:Annotated[AsyncSession, Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user_update.username is not None and user_update.username  != user.username :
        result =await db.execute(select(models.User).where(func.lower(models.User.username) == user_update.username.lower()))
        existing_user= result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username already exist")
    
    if user_update.email is not None and user_update.email != user.email :
        result = await db.execute(select(models.User).where(func.lower(models.User.email) == user_update.email.lower()))
        existing_email = result.scalars().first()
        if existing_email :
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email already exist")
        
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email.lower()
    if user_update.image_file is not None:
        user.image_file= user_update.image_file

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}/posts",response_model=list[PostResponse])
async def get_user_posts(user_id: int, db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id==user_id))
    user= result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    
    result =await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id==user_id))
    posts=result.scalars().all()
    return posts

@router.delete("/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def user_delete(user_id: int, db: Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id ==  user_id))
    user= result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="user not found")
    
    await db.delete(user)
    await db.commit()