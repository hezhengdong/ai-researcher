"""SQLite persistence layer for surveys, papers, sections, and chapters."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, relationship

DATABASE_URL = "sqlite:///surveys.db"
engine = create_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True)
    topic = Column(String, nullable=False)
    status = Column(String, default="running")
    draft = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    papers = relationship("Paper", back_populates="survey", cascade="all, delete-orphan")
    sections = relationship("Section", back_populates="survey", cascade="all, delete-orphan")
    chapters = relationship("Chapter", back_populates="survey", cascade="all, delete-orphan")



class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    paper_id = Column(String, nullable=False)
    title = Column(String)
    authors = Column(JSON, default=list)
    year = Column(Integer)
    citation_count = Column(Integer)
    abstract = Column(Text, default="")
    markdown = Column(Text, default="")
    source_type = Column(String, default="none")

    survey = relationship("Survey", back_populates="papers")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    sort_order = Column(Integer)
    title = Column(String)
    theme = Column(String)
    paper_ids = Column(JSON, default=list)

    survey = relationship("Survey", back_populates="sections")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    sort_order = Column(Integer)
    title = Column(String)
    content = Column(Text)

    survey = relationship("Survey", back_populates="chapters")


Base.metadata.create_all(engine)


def create_survey(topic: str) -> int:
    """Create a running survey at pipeline start. Returns survey id."""
    with Session(engine) as session:
        survey = Survey(topic=topic, status="running")
        session.add(survey)
        session.commit()
        return survey.id


def update_survey_done(survey_id: int, state: dict):
    """Update survey status to done and persist all related data."""
    with Session(engine) as session:
        survey = session.query(Survey).filter_by(id=survey_id).first()
        if not survey:
            return
        survey.status = "done"
        survey.draft = state.get("draft", "")

        for p in state.get("papers", []):
            session.add(Paper(
                survey_id=survey_id,
                paper_id=p["id"],
                title=p.get("title", ""),
                authors=p.get("authors", []),
                year=p.get("year"),
                citation_count=p.get("citation_count"),
                abstract=p.get("abstract", ""),
                markdown=p.get("markdown", ""),
                source_type=p.get("source_type", "none"),
            ))

        for i, sec in enumerate(state.get("outline", [])):
            session.add(Section(
                survey_id=survey_id,
                sort_order=i,
                title=sec["title"],
                theme=sec.get("theme", ""),
                paper_ids=sec.get("paper_ids", []),
            ))

        chapters = state.get("chapters", [])
        outline = state.get("outline", [])
        for i, ch in enumerate(chapters):
            title = outline[i]["title"] if i < len(outline) else f"Chapter {i+1}"
            session.add(Chapter(
                survey_id=survey_id,
                sort_order=i,
                title=title,
                content=ch,
            ))

        session.commit()



def list_surveys() -> list[dict]:
    """Return all surveys ordered by creation time descending."""
    with Session(engine) as session:
        rows = session.query(Survey).order_by(Survey.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "topic": r.topic,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "draft_preview": (r.draft or "")[:200],
            }
            for r in rows
        ]


def get_survey(survey_id: int) -> dict | None:
    """Return full survey detail including papers, sections, and chapters."""
    with Session(engine) as session:
        survey = session.query(Survey).filter_by(id=survey_id).first()
        if not survey:
            return None

        return {
            "id": survey.id,
            "topic": survey.topic,
            "status": survey.status,
            "draft": survey.draft,
            "created_at": survey.created_at.isoformat(),
            "papers": [
                {
                    "paper_id": p.paper_id,
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "citation_count": p.citation_count,
                    "abstract": p.abstract,
                    "markdown": p.markdown,
                    "source_type": p.source_type,
                }
                for p in survey.papers
            ],
            "sections": [
                {
                    "sort_order": s.sort_order,
                    "title": s.title,
                    "theme": s.theme,
                    "paper_ids": s.paper_ids,
                }
                for s in sorted(survey.sections, key=lambda x: x.sort_order)
            ],
            "chapters": [
                {
                    "sort_order": c.sort_order,
                    "title": c.title,
                    "content": c.content,
                }
                for c in sorted(survey.chapters, key=lambda x: x.sort_order)
            ],


        }
