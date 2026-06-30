# WHAT DOES THIS FILE DO: re-exports everything from db sub-modules so workflow_db.py shim stays clean

from .connection import (
    Base, engine, SessionLocal, session_scope,
    normalize_query, _run_migrations, init_workflow_db,
)

from .models import (
    PredefinedQuestion, FlaggedResponse, Correction, BlockedWord,
    SystemSetting, AuditLog, UploadDocument, UploadChunk,
    Department, AdminUser,
)

from .audit import (
    log_audit_action, list_audit_logs, get_workflow_summary,
)

from .blocked_words import (
    get_blocked_words_list, is_question_blocked,
    list_blocked_words, add_blocked_word, delete_blocked_word,
)

from .corrections import (
    find_best_correction, list_corrections, create_direct_correction,
)

from .flagged import (
    create_flagged_response, list_flagged_responses,
    approve_flagged_response, reject_flagged_response,
)

from .uploads import (
    create_upload_document, save_upload_chunks, mark_upload_failed,
    list_upload_documents, delete_upload_document, get_upload_document,
    get_active_upload_chunks, update_upload_s3_key,
)

from .settings import (
    get_system_setting, set_system_setting, get_predefined_questions,
)

from .departments import (
    list_departments, create_department, update_department, delete_department,
)

from .users import (
    list_users, get_user_by_email, create_user, update_user, deactivate_user,
)

from .exports import (
    export_chat_logs,
    export_blocked_interactions,
    export_corrections,
    export_flagged_responses,
    export_visitor_sessions,
    export_audit_log,
    export_blocked_words,
)
