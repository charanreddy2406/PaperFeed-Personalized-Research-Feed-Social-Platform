"""Generate deterministic fictional notes linked to real public papers."""
import random,os
from paperfeed import db,auth,posts
from paperfeed.schemas import PostIn
PAPERS=[('https://arxiv.org/abs/1706.03762','Attention Is All You Need','transformers'),('https://arxiv.org/abs/2005.11401','Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks','rag'),('https://arxiv.org/abs/1512.03385','Deep Residual Learning for Image Recognition','computer vision'),('https://arxiv.org/abs/2303.11366','PaLM-E: An Embodied Multimodal Language Model','robotics')]
def main():
    rng=random.Random(42); db.open_pool()
    try:
        users=[]
        with db.transaction() as c:
            for i in range(20):
                name=f'synthetic-{i:03}'
                c.execute('INSERT INTO users(username,display_name,password_hash,interests) VALUES(%s,%s,%s,%s) ON CONFLICT(username) DO NOTHING',(name,name,auth.hasher.hash(os.urandom(32).hex()),[PAPERS[i%4][2]]))
                users.append(c.execute('SELECT id FROM users WHERE username=%s',(name,)).fetchone()['id'])
        for i in range(80):
            url,title,tag=PAPERS[i%4]
            posts.create(rng.choice(users),PostIn(paper_url=url,paper_title=title,title=f'Research note {i+1}: {title}',content='Synthetic discussion prompt: Which assumptions should be tested before applying this method to a new dataset?',tags=[tag]))
    finally: db.close_pool()
if __name__=='__main__': main()
