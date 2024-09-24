from sqlalchemy import Column, Integer, String

from source_db import Base


class SourceFile(Base):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, unique=True, index=True)
    file_path = Column(String, index=True)


