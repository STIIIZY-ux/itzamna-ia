"""Learning Engine: conceptos, preguntas, quizzes, flashcards, libros y capítulos.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- concepts ---
    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("mastery", sa.Float(), server_default="0", nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_concepts_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name="fk_concepts_subject_id_subjects", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_concepts"),
        sa.UniqueConstraint("user_id", "name", name="uq_concepts_user_name"),
    )
    op.create_index("ix_concepts_user_id", "concepts", ["user_id"], unique=False)

    # --- books ---
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=True),
        sa.Column("num_chapters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_books_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_books"),
    )
    op.create_index("ix_books_user_id", "books", ["user_id"], unique=False)
    op.create_check_constraint(
        "ck_books_status", "books", "status IN ('pending', 'processing', 'ready', 'failed')"
    )

    # --- chapters ---
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pendiente", nullable=False),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], name="fk_chapters_book_id_books", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chapters_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_chapters"),
        sa.UniqueConstraint("book_id", "order_index", name="uq_chapters_book_order"),
    )
    op.create_index("ix_chapters_book_id", "chapters", ["book_id"], unique=False)
    op.create_index("ix_chapters_user_id", "chapters", ["user_id"], unique=False)
    op.create_check_constraint(
        "ck_chapters_status",
        "chapters",
        "status IN ('pendiente', 'en_lectura', 'leido', 'control_pendiente', 'control_completado', 'repaso')",
    )

    # --- questions ---
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("book_id", sa.Integer(), nullable=True),
        sa.Column("chapter_id", sa.Integer(), nullable=True),
        sa.Column("question_type", sa.String(length=50), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correct_index", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.Integer(), server_default="2", nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_questions_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], name="fk_questions_concept_id_concepts", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name="fk_questions_subject_id_subjects", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], name="fk_questions_book_id_books", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], name="fk_questions_chapter_id_chapters", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
    )
    op.create_index("ix_questions_user_id", "questions", ["user_id"], unique=False)
    op.create_check_constraint(
        "ck_questions_question_type",
        "questions",
        "question_type IN ('multiple_choice', 'true_false', 'short_answer', 'open_answer', 'exercise')",
    )

    # --- quizzes ---
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quiz_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_quizzes_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_quizzes"),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"], unique=False)
    op.create_check_constraint(
        "ck_quizzes_quiz_type",
        "quizzes",
        "quiz_type IN ('task', 'subject', 'concept', 'chapter', 'cumulative', 'final')",
    )
    op.create_check_constraint(
        "ck_quizzes_status", "quizzes", "status IN ('draft', 'in_progress', 'completed')"
    )

    # --- quiz_questions ---
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name="fk_quiz_questions_quiz_id_quizzes", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name="fk_quiz_questions_question_id_questions", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_questions"),
        sa.UniqueConstraint("quiz_id", "question_id", name="uq_quiz_questions_quiz_question"),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"], unique=False)

    # --- quiz_answers ---
    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=True),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_quiz_answers_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name="fk_quiz_answers_quiz_id_quizzes", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name="fk_quiz_answers_question_id_questions", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_answers"),
        sa.UniqueConstraint("quiz_id", "question_id", "user_id", name="uq_quiz_answers_once"),
    )
    op.create_index("ix_quiz_answers_user_id", "quiz_answers", ["user_id"], unique=False)

    # --- flashcards ---
    op.create_table(
        "flashcards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=True),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.Integer(), server_default="2", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="new", nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_flashcards_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], name="fk_flashcards_concept_id_concepts", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_flashcards"),
    )
    op.create_index("ix_flashcards_user_id", "flashcards", ["user_id"], unique=False)
    op.create_check_constraint(
        "ck_flashcards_status", "flashcards", "status IN ('new', 'learning', 'review')"
    )


def downgrade() -> None:
    op.drop_table("flashcards")
    op.drop_table("quiz_answers")
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")
    op.drop_table("questions")
    op.drop_table("chapters")
    op.drop_table("books")
    op.drop_table("concepts")
