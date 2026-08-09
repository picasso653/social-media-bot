from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.models.user import Base


class PostPlatform(Base):
    __tablename__ = "post_platforms"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id = Column(PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(PGUUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(50), nullable=False)
    platform_post_id = Column(String(255), nullable=True)
    platform_post_url = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    posted_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    post = relationship("Post", back_populates="post_platforms")
    account = relationship("SocialAccount", back_populates="post_platforms")
