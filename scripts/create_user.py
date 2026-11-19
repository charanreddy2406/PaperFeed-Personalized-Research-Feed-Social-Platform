import argparse,getpass
from paperfeed import db,auth

def main():
    p=argparse.ArgumentParser(); p.add_argument('username'); p.add_argument('display_name'); a=p.parse_args()
    password=getpass.getpass('Password: ')
    if len(password)<12: raise SystemExit('Minimum 12 characters')
    db.open_pool()
    try:
        with db.transaction() as c: c.execute('INSERT INTO users(username,display_name,password_hash) VALUES(%s,%s,%s)',(a.username,a.display_name,auth.hasher.hash(password)))
    finally: db.close_pool()
if __name__=='__main__': main()
