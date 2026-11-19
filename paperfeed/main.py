from contextlib import asynccontextmanager
import logging,secrets
from uuid import UUID
from fastapi import FastAPI,Depends,HTTPException,Request,Response,Query,APIRouter
from fastapi.responses import JSONResponse
from paperfeed import db,auth,posts,media,schemas
from paperfeed.config import settings
from paperfeed.cache import FeedCache
from paperfeed.feed import get_feed

logging.basicConfig(level=logging.INFO)
@asynccontextmanager
async def lifespan(app):
    db.open_pool()
    try: yield
    finally: db.close_pool()
app=FastAPI(title='PaperFeed',lifespan=lifespan)
router=APIRouter(prefix='/api/v1')
@app.middleware('http')
async def security(request,call_next):
    try: auth.check_origin(request)
    except HTTPException as exc: return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response
@app.get('/health')
def health():
    with db.transaction() as c: c.execute('SELECT 1')
    return {'status':'ok'}
@router.post('/auth/login')
def login(data:schemas.Login,response:Response,request:Request):
    from paperfeed.limits import enforce
    enforce("login-ip", request.client.host if request.client else "unknown", 30, 60)
    enforce("login-account", data.username.casefold(), 10, 300)
    with db.transaction() as c:
        u=c.execute('SELECT * FROM users WHERE username=%s',(data.username,)).fetchone()
        if not u or not auth.verify(data.password,u['password_hash']): raise HTTPException(401,'Invalid credentials')
        token=secrets.token_urlsafe(32)
        c.execute("INSERT INTO sessions VALUES(%s,%s,now()+interval '12 hours')",(auth.digest(token),u['id']))
    response.set_cookie('session',token,httponly=True,secure=settings.secure_cookie,samesite='strict',max_age=43200)
    return {'id':u['id'],'display_name':u['display_name']}
@router.post('/auth/logout')
def logout(request:Request,response:Response,user=Depends(auth.current_user)):
    with db.transaction() as c: c.execute('DELETE FROM sessions WHERE token_hash=%s',(auth.digest(request.cookies['session']),))
    response.delete_cookie('session'); return {'ok':True}
@router.get('/users/me')
def me(user=Depends(auth.current_user)): return user
@router.patch('/users/me')
def profile(data:schemas.Profile,user=Depends(auth.current_user)):
    with db.transaction() as c: c.execute('UPDATE users SET display_name=%s,interests=%s,feed_version=feed_version+1 WHERE id=%s',(data.display_name,data.interests,user['id']))
    FeedCache().invalidate(user['id']); return {'ok':True}
@router.get('/papers')
def papers(q:str='',user=Depends(auth.current_user)):
    with db.transaction() as c: return c.execute('SELECT * FROM papers WHERE title ILIKE %s ORDER BY id DESC LIMIT 50',('%'+q+'%',)).fetchall()
@router.get('/papers/{pid}')
def paper(pid:int,user=Depends(auth.current_user)):
    with db.transaction() as c: row=c.execute('SELECT * FROM papers WHERE id=%s',(pid,)).fetchone()
    if not row: raise HTTPException(404,'Paper not found')
    return row
@router.post('/posts',status_code=201)
def create(data:schemas.PostIn,user=Depends(auth.current_user)):
    from paperfeed.limits import enforce
    enforce('post', str(user['id']), 30, 3600)
    return posts.create(user['id'],data)
@router.get('/posts/{pid}')
def read(pid:int,user=Depends(auth.current_user)):
    items=posts.hydrate([pid],user['id'])
    if not items: raise HTTPException(404,'Post not found')
    return items[0]
@router.patch('/posts/{pid}')
def edit(pid:int,data:schemas.EditPost,user=Depends(auth.current_user)):
    with db.transaction() as c:
        row=c.execute('UPDATE posts SET title=%s,content=%s,tags=%s,embedding=NULL,updated_at=now() WHERE id=%s AND author_id=%s RETURNING id',(data.title,data.content,data.tags,pid,user['id'])).fetchone()
        if not row: raise HTTPException(403,'Not permitted')
        posts.event(c,user['id'],pid,'embed')
    return {'ok':True}
@router.delete('/posts/{pid}')
def delete(pid:int,user=Depends(auth.current_user)):
    with db.transaction() as c:
        row=c.execute('DELETE FROM posts WHERE id=%s AND author_id=%s RETURNING id',(pid,user['id'])).fetchone()
        if not row: raise HTTPException(403,'Not permitted')
    return {'ok':True}
@router.get('/feed')
def feed(limit:int=Query(20,ge=1,le=50),cursor:str|None=None,user=Depends(auth.current_user)): return get_feed(user,limit,cursor)
@router.post('/media/uploads')
def upload(data:schemas.Upload,user=Depends(auth.current_user)):
    from paperfeed.limits import enforce
    enforce("upload", str(user["id"]), 20, 3600)
    return media.upload(user["id"],data.content_type,data.size_bytes)
@router.post('/media/{mid}/complete')
def complete(mid:UUID,user=Depends(auth.current_user)): return media.complete(user['id'],mid)
@router.put('/posts/{pid}/like')
def like(pid:int,user=Depends(auth.current_user)): return posts.relationship(user['id'],pid,'likes',True)
@router.delete('/posts/{pid}/like')
def unlike(pid:int,user=Depends(auth.current_user)): return posts.relationship(user['id'],pid,'likes',False)
@router.put('/posts/{pid}/bookmark')
def save(pid:int,user=Depends(auth.current_user)): return posts.relationship(user['id'],pid,'bookmarks',True)
@router.delete('/posts/{pid}/bookmark')
def unsave(pid:int,user=Depends(auth.current_user)): return posts.relationship(user['id'],pid,'bookmarks',False)
@router.get('/bookmarks')
def bookmarks(user=Depends(auth.current_user)):
    with db.transaction() as c: ids=[r['post_id'] for r in c.execute('SELECT post_id FROM bookmarks WHERE user_id=%s ORDER BY post_id DESC LIMIT 100',(user['id'],))]
    return posts.hydrate(ids,user['id'])
@router.post('/posts/{pid}/comments',status_code=201)
def comment(pid:int,data:schemas.Comment,user=Depends(auth.current_user)):
    from paperfeed.limits import enforce
    enforce('comment', str(user['id']), 60, 60)
    with db.transaction() as c:
        if not c.execute('SELECT id FROM posts WHERE id=%s FOR KEY SHARE',(pid,)).fetchone(): raise HTTPException(404,'Post not found')
        row=c.execute('INSERT INTO comments(user_id,post_id,content) VALUES(%s,%s,%s) RETURNING id',(user['id'],pid,data.content)).fetchone(); posts.event(c,user['id'],pid,'comment')
    return row
@router.get('/posts/{pid}/comments')
def comments(pid:int,user=Depends(auth.current_user)):
    with db.transaction() as c: return c.execute('SELECT c.id,c.content,c.created_at,u.display_name FROM comments c JOIN users u ON u.id=c.user_id WHERE post_id=%s ORDER BY c.id LIMIT 100',(pid,)).fetchall()
def follow_change(uid,user,enabled):
    if uid==user: raise HTTPException(422,'Cannot follow yourself')
    with db.transaction() as c:
        if not c.execute('SELECT id FROM users WHERE id=%s',(uid,)).fetchone(): raise HTTPException(404,'User not found')
        if enabled: c.execute('INSERT INTO follows VALUES(%s,%s) ON CONFLICT DO NOTHING',(user,uid))
        else: c.execute('DELETE FROM follows WHERE follower_id=%s AND followee_id=%s',(user,uid))
        c.execute('UPDATE users SET feed_version=feed_version+1 WHERE id=%s',(user,))
    FeedCache().invalidate(user); return {'active':enabled}
@router.put('/users/{uid}/follow')
def follow(uid:int,user=Depends(auth.current_user)): return follow_change(uid,user['id'],True)
@router.delete('/users/{uid}/follow')
def unfollow(uid:int,user=Depends(auth.current_user)): return follow_change(uid,user['id'],False)
@router.post('/events',status_code=202)
def interaction(data:schemas.Interaction,user=Depends(auth.current_user)):
    from paperfeed.limits import enforce
    enforce("interaction", str(user["id"]), 120, 60)
    with db.transaction() as c:
        if not c.execute('SELECT id FROM posts WHERE id=%s FOR KEY SHARE',(data.post_id,)).fetchone(): raise HTTPException(404,'Post not found')
        posts.event(c,user['id'],data.post_id,data.event_type)
    return {'accepted':True}
app.include_router(router)
