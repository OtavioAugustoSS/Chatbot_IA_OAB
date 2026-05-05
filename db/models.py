from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from db.database import Base


class Usuario(Base):
    __tablename__ = 'usuarios'

    telefone = Column(String(20), primary_key=True, index=True)
    nome_cliente = Column(String(100), nullable=True)
    bot_ativo = Column(Boolean, default=True)
    data_ultima_interacao = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    historico = relationship("HistoricoConversa", back_populates="usuario", cascade="all, delete-orphan")


class HistoricoConversa(Base):
    __tablename__ = 'historico_conversas'

    id = Column(Integer, primary_key=True, index=True)
    telefone_usuario = Column(String(20))
    mensagem_cliente = Column(Text, nullable=True)
    resposta_bot = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="historico")
