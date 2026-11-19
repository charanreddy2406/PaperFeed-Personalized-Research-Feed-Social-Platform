from paperfeed.ranking import Features,score,merge_candidates,diversify
from paperfeed.auth import digest,verify,hasher
from paperfeed.schemas import PostIn
from paperfeed.config import settings
from paperfeed.main import app

def test_relevance():
    assert score(Features(1,1,1,False,0,0))>score(Features(0,0,1,False,0,0))
def test_dedupe():
    assert merge_candidates([[{'id':1},{'id':2}],[{'id':1},{'id':3}]])==[{'id':1},{'id':2},{'id':3}]
def test_diversity():
    p=[{'id':i,'author_id':a} for i,a in enumerate([1,1,1,2])]
    assert [x['id'] for x in diversify(p)]==[0,1,3,2]
def test_password():
    h=hasher.hash('example-password'); assert verify('example-password',h); assert not verify('wrong',h); assert digest('a')!=digest('b')
def test_ttl(): assert settings.ttl==180
def test_routes():
    paths=app.openapi()['paths']; assert '/api/v1/feed' in paths; assert 'put' in paths['/api/v1/posts/{pid}/like']
def test_tags():
    p=PostIn(paper_url='https://arxiv.org/abs/1234',paper_title='Paper',title='Notes',content='Text',tags=[' RAG ','rag']); assert p.tags==['rag']
