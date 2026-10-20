from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    text = Column(Text)
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    questions = relationship("Question", cascade="all, delete-orphan", back_populates="document")
    cards = relationship("Card", cascade="all, delete-orphan", back_populates="document")


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    question = Column(Text)
    options = Column(JSON)          # seznam 4 odpovědí
    correct = Column(Integer)       # index správné (0-3)
    explanation = Column(Text, default="")
    document = relationship("Document", back_populates="questions")


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    front = Column(Text)
    back = Column(Text)
    box = Column(Integer, default=1)               # Leitnerova krabička 1-5
    next_review = Column(Date, default=date.today)  # kdy se má znovu zopakovat
    document = relationship("Document", back_populates="cards")