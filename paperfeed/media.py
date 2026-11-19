import uuid
import io
from PIL import Image
from botocore.exceptions import ClientError
import boto3
from botocore.config import Config
from fastapi import HTTPException
from paperfeed.config import settings
from paperfeed.db import transaction

TYPES={'image/png':5_000_000,'image/jpeg':5_000_000,'video/mp4':25_000_000}
def client(public=False):
    return boto3.client('s3',endpoint_url=(settings.public_endpoint or settings.endpoint) if public else settings.endpoint,config=Config(signature_version='s3v4',s3={'addressing_style':'path'}))
def upload(user,kind,size):
    if kind not in TYPES or not 0<size<=TYPES[kind]: raise HTTPException(422,'Unsupported media or size')
    mid=uuid.uuid4(); key=f'media/{user}/{mid}'
    with transaction() as c:
        c.execute('INSERT INTO media(id,owner_id,object_key,content_type,size_bytes,state) VALUES(%s,%s,%s,%s,%s,\'pending\')',(mid,user,key,kind,size))
    form=client(True).generate_presigned_post(settings.bucket,f"staging/{user}/{mid}",Fields={'Content-Type':kind},Conditions=[{'Content-Type':kind},['content-length-range',size,size]],ExpiresIn=300)
    return {'id':str(mid),**form}
def complete(user,mid):
    with transaction() as c:
        row=c.execute('SELECT * FROM media WHERE id=%s AND owner_id=%s FOR UPDATE',(mid,user)).fetchone()
        if not row or row['state']!='pending': raise HTTPException(404,'Pending upload not found')
        storage = client()
        staging = f'staging/{user}/{mid}'
        try:
            obj = storage.get_object(Bucket=settings.bucket, Key=staging)
        except ClientError as exc:
            raise HTTPException(422, 'Upload not available') from exc
        with obj['Body'] as body:
            content = body.read(row['size_bytes'] + 1)
        if len(content) != row['size_bytes'] or obj['ContentType'] != row['content_type']:
            raise HTTPException(422, 'Media mismatch')
        try:
            if row['content_type'].startswith('image/'):
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != {'image/png':'PNG','image/jpeg':'JPEG'}[row['content_type']]:
                        raise ValueError('Wrong format')
                    image.verify()
            elif len(content) < 12 or content[4:8] != b'ftyp':
                raise ValueError('Invalid MP4 header')
        except (ValueError, OSError, Image.DecompressionBombError) as exc:
            raise HTTPException(422, 'Invalid media') from exc
        storage.put_object(Bucket=settings.bucket, Key=row['object_key'], Body=content, ContentType=row['content_type'])
        c.execute("UPDATE media SET state='uploaded' WHERE id=%s",(mid,))
    return {'id':str(mid),'state':'uploaded'}
def read_url(key):
    return client(True).generate_presigned_url('get_object',Params={'Bucket':settings.bucket,'Key':key},ExpiresIn=300)
