from uuid import UUID
from pydantic import BaseModel,Field,HttpUrl,field_validator
from typing import Literal
class Login(BaseModel):
    username:str=Field(min_length=1,max_length=80)
    password:str=Field(min_length=1,max_length=256)
class PostIn(BaseModel):
    paper_url:HttpUrl
    paper_title:str=Field(min_length=1,max_length=300)
    abstract:str=Field(default='',max_length=10000)
    title:str=Field(min_length=1,max_length=300)
    content:str=Field(min_length=1,max_length=12000)
    tags:list[str]=Field(default_factory=list,max_length=15)
    media_ids:list[UUID]=Field(default_factory=list,max_length=4)
    @field_validator('tags')
    @classmethod
    def normalize(cls,v): return normalize_tags(v)
class EditPost(BaseModel):
    title:str=Field(min_length=1,max_length=300)
    content:str=Field(min_length=1,max_length=12000)
    tags:list[str]=Field(default_factory=list,max_length=15)
    @field_validator('tags')
    @classmethod
    def normalize(cls,v): return normalize_tags(v)
def normalize_tags(values):
    if any(len(t)>80 for t in values): raise ValueError('Tag too long')
    return sorted({t.strip().lower() for t in values if t.strip()})
class Profile(BaseModel):
    display_name:str=Field(min_length=1,max_length=100)
    interests:list[str]=Field(max_length=20)
    @field_validator('interests')
    @classmethod
    def normalize(cls,v): return normalize_tags(v)
class Comment(BaseModel):
    content:str=Field(min_length=1,max_length=3000)
class Upload(BaseModel):
    content_type:str
    size_bytes:int=Field(gt=0,le=25000000)
class Interaction(BaseModel):
    post_id:int
    event_type:Literal['impression','paper_click']
