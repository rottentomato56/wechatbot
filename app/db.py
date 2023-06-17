import redis
import settings
from sqlalchemy import create_engine, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Text, UnicodeText
from sqlalchemy.sql import func 

engine = create_engine(settings.SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

cache = redis.from_url(settings.REDIS_URL, decode_responses=True)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # for wechat users it is openid, otherwise 'system' or 'ai'
    date_joined = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)

    sender_id = Column(Integer, ForeignKey('users.id'))
    sender = relationship('User', foreign_keys=[sender_id], backref='sent_messages')

    receiver_id = Column(Integer, ForeignKey('users.id'))
    receiver = relationship('User', foreign_keys=[receiver_id], backref='received_messages')

    msg_type = Column(String, default='text')
    time_sent = Column(DateTime(timezone=True), server_default=func.now())
    content = Column(UnicodeText)
    media_id = Column(String) # used for wechat for voice/img/video messages


def create_tables():
    Base.metadata.create_all(engine)

def drop_tables():
    Base.metadata.drop_all(engine)

def get_or_create_user(session, username):
    user = session.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user

def log_message(session, sender, receiver, **kwargs):
    content=kwargs.get('content')
    msg_type = kwargs.get('msg_type', 'text')
    media_id = kwargs.get('media_id')
    message = Message(sender=sender, receiver=receiver, msg_type=msg_type, content=content, media_id=media_id)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message

def get_latest_received_message(session, user):
    message = session.query(Message).filter(Message.receiver_id == user.id).order_by(desc('time_sent')).first()
    return message

def init_db():
    session = SessionLocal()
    system = get_or_create_user(session, 'system')
    assistant = get_or_create_user(session, 'assistant')
    session.close()
    return True



