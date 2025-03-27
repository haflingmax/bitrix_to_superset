import os
import logging
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import requests
import threading
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

logging.basicConfig(level=logging.INFO, filename="app.log", format="%(asctime)s %(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
BITRIX_URL = os.getenv("BITRIX_URL")

if not DATABASE_URL or not BITRIX_URL:
    raise ValueError("DATABASE_URL or BITRIX_URL not set")
logger.info(f"DATABASE_URL: {DATABASE_URL}")

sync_status = {
    "deals": {"running": False, "progress": 0, "total": 0, "last_run": None, "stop_requested": False},
    "tasks": {"running": False, "progress": 0, "total": 0, "last_run": None, "stop_requested": False},
    "projects": {"running": False, "progress": 0, "total": 0, "last_run": None, "stop_requested": False},
}

def check_bitrix_status():
    url = f"{BITRIX_URL}app.info"
    try:
        response = requests.get(url, timeout=5, verify=False)
        response.raise_for_status()
        data = response.json()
        return {"available": True, "license": data.get("result", {}).get("LICENSE", "N/A"), "scopes": data.get("result", {}).get("SCOPE", [])}
    except requests.RequestException as e:
        logger.error(f"Bitrix24 status check failed: {e}")
        return {"available": False, "license": "N/A", "scopes": []}

def get_count_from_db(table):
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Error counting {table}: {e}")
        return 0

def get_max_id_from_db(table):
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT MAX(id::integer) FROM {table}")
                result = cur.fetchone()[0]
                return str(result) if result is not None else None
    except Exception as e:
        logger.error(f"Error getting max id from {table}: {e}")
        return None

def get_count_from_bitrix(entity):
    try:
        if entity == "deals":
            url = f"{BITRIX_URL}crm.deal.list"
            params = {"SELECT[]": "ID"}
        elif entity == "tasks":
            url = f"{BITRIX_URL}tasks.task.list"
            params = {"SELECT[]": "ID"}
        elif entity == "projects":
            url = f"{BITRIX_URL}sonet_group.get"
            params = {"SELECT[]": "ID"}
        response = requests.get(url, params=params, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        if entity == "projects":
            return len(data["result"])
        return data["total"] if "total" in data else 0
    except requests.RequestException as e:
        logger.error(f"Error fetching {entity} count from Bitrix: {e}")
        return 0

def sync_entity(entity, batch_size=50):
    sync_status[entity]["running"] = True
    sync_status[entity]["last_run"] = datetime.now().isoformat()
    sync_status[entity]["stop_requested"] = False  # Сбрасываем флаг остановки
    try:
        total = get_count_from_bitrix(entity)
        sync_status[entity]["total"] = total
        
        last_synced_id = get_max_id_from_db(entity)
        start = 0
        if last_synced_id:
            logger.info(f"Resuming {entity} sync from last_synced_id: {last_synced_id}")
            sync_status[entity]["progress"] = get_count_from_db(entity)
        else:
            logger.info(f"Starting {entity} sync from scratch")
            sync_status[entity]["progress"] = 0

        while True:
            if sync_status[entity]["stop_requested"]:
                logger.info(f"Sync for {entity} stopped by user")
                break

            if entity == "deals":
                url = f"{BITRIX_URL}crm.deal.list"
                insert_func = insert_deal
                params = {"start": start, "SELECT[]": "*"}
                if last_synced_id:
                    params["filter[>ID]"] = last_synced_id
            elif entity == "tasks":
                url = f"{BITRIX_URL}tasks.task.list"
                insert_func = insert_task
                params = {"order[ID]": "ASC", "start": start, "select[]": "*"}
                if last_synced_id:
                    params["filter[>ID]"] = last_synced_id
            elif entity == "projects":
                url = f"{BITRIX_URL}sonet_group.get"
                insert_func = insert_project
                params = {"start": start, "SELECT[]": "*"}
                if last_synced_id:
                    params["filter[>ID]"] = last_synced_id

            response = requests.get(url, params=params, timeout=120, verify=False)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Response for {entity} at start {start}: {data}")

            if "result" not in data:
                logger.error(f"No 'result' in response for {entity}: {data}")
                break

            items = data["result"]["tasks"] if entity == "tasks" else data["result"]
            if not isinstance(items, list):
                logger.error(f"Items is not a list for {entity}: {items}")
                break

            for item in items:
                if sync_status[entity]["stop_requested"]:
                    logger.info(f"Sync for {entity} stopped by user during item processing")
                    break
                if not isinstance(item, dict) or ("ID" not in item and "id" not in item):
                    logger.error(f"Invalid item in {entity}: {item}")
                    continue
                insert_func(item)
                sync_status[entity]["progress"] += 1

            if "next" not in data or sync_status[entity]["progress"] >= total:
                break
            start = data["next"]

        logger.info(f"Synchronized {entity}: {sync_status[entity]['progress']} of {total} items")
    except Exception as e:
        logger.error(f"Sync {entity} failed: {e}")
    finally:
        sync_status[entity]["running"] = False
        sync_status[entity]["stop_requested"] = False  # Сбрасываем флаг после завершения

def clear_table(entity):
    table_map = {"deals": "deals", "tasks": "tasks", "projects": "projects"}
    if entity not in table_map:
        logger.error(f"Invalid entity for clear: {entity}")
        return
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {table_map[entity]}")
                conn.commit()
        logger.info(f"Table {entity} cleared")
        sync_status[entity]["progress"] = 0
    except Exception as e:
        logger.error(f"Failed to clear table {entity}: {e}")

def insert_deal(data):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            amount = float(data.get("OPPORTUNITY", 0) or 0)
            cur.execute("""
                INSERT INTO deals (id, title, amount, status, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE 
                SET title = EXCLUDED.title, 
                    amount = EXCLUDED.amount,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """, (data["ID"], data["TITLE"], amount, data["STAGE_ID"]))
            conn.commit()

def convert_yn_to_bool(value):
    if value == "Y":
        return True
    elif value == "N":
        return False
    return False

def insert_task(data):
    try:
        logger.info(f"Inserting task: {data}")
        accomplices = json.dumps(data.get("accomplices", []))
        auditors = json.dumps(data.get("auditors", []))
        group = json.dumps(data.get("group", []))
        accomplices_data = json.dumps(data.get("accomplicesData", []))
        auditors_data = json.dumps(data.get("auditorsData", []))
        creator_id = data.get("creator", {}).get("id", "0")
        responsible_id = data.get("responsible", {}).get("id", "0")
        status_changed_by = data.get("statusChangedBy")

        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks (
                        id, parent_id, title, description, mark, priority, multitask, not_viewed, replicate,
                        stage_id, created_by, created_date, responsible_id, changed_by, changed_date,
                        status_changed_by, closed_by, closed_date, activity_date, date_start, deadline,
                        start_date_plan, end_date_plan, guid, xml_id, comments_count, service_comments_count,
                        allow_change_deadline, allow_time_tracking, task_control, add_in_report,
                        forked_by_template_id, time_estimate, time_spent_in_logs, match_work_time,
                        forum_topic_id, forum_id, site_id, subordinate, exchange_modified, exchange_id,
                        outlook_version, viewed_date, sorting, duration_plan, duration_fact, duration_type,
                        is_muted, is_pinned, is_pinned_in_group, flow_id, description_in_bbcode, status,
                        status_changed_date, favorite, group_id, auditors, accomplices, new_comments_count,
                        "group", creator, responsible, accomplices_data, auditors_data, sub_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        parent_id = EXCLUDED.parent_id, title = EXCLUDED.title, description = EXCLUDED.description,
                        mark = EXCLUDED.mark, priority = EXCLUDED.priority, multitask = EXCLUDED.multitask,
                        not_viewed = EXCLUDED.not_viewed, replicate = EXCLUDED.replicate,
                        stage_id = EXCLUDED.stage_id, created_by = EXCLUDED.created_by,
                        created_date = EXCLUDED.created_date, responsible_id = EXCLUDED.responsible_id,
                        changed_by = EXCLUDED.changed_by, changed_date = EXCLUDED.changed_date,
                        status_changed_by = EXCLUDED.status_changed_by, closed_by = EXCLUDED.closed_by,
                        closed_date = EXCLUDED.closed_date, activity_date = EXCLUDED.activity_date,
                        date_start = EXCLUDED.date_start, deadline = EXCLUDED.deadline,
                        start_date_plan = EXCLUDED.start_date_plan, end_date_plan = EXCLUDED.end_date_plan,
                        guid = EXCLUDED.guid, xml_id = EXCLUDED.xml_id, comments_count = EXCLUDED.comments_count,
                        service_comments_count = EXCLUDED.service_comments_count,
                        allow_change_deadline = EXCLUDED.allow_change_deadline,
                        allow_time_tracking = EXCLUDED.allow_time_tracking, task_control = EXCLUDED.task_control,
                        add_in_report = EXCLUDED.add_in_report, forked_by_template_id = EXCLUDED.forked_by_template_id,
                        time_estimate = EXCLUDED.time_estimate, time_spent_in_logs = EXCLUDED.time_spent_in_logs,
                        match_work_time = EXCLUDED.match_work_time, forum_topic_id = EXCLUDED.forum_topic_id,
                        forum_id = EXCLUDED.forum_id, site_id = EXCLUDED.site_id, subordinate = EXCLUDED.subordinate,
                        exchange_modified = EXCLUDED.exchange_modified, exchange_id = EXCLUDED.exchange_id,
                        outlook_version = EXCLUDED.outlook_version, viewed_date = EXCLUDED.viewed_date,
                        sorting = EXCLUDED.sorting, duration_plan = EXCLUDED.duration_plan,
                        duration_fact = EXCLUDED.duration_fact, duration_type = EXCLUDED.duration_type,
                        is_muted = EXCLUDED.is_muted, is_pinned = EXCLUDED.is_pinned,
                        is_pinned_in_group = EXCLUDED.is_pinned_in_group, flow_id = EXCLUDED.flow_id,
                        description_in_bbcode = EXCLUDED.description_in_bbcode, status = EXCLUDED.status,
                        status_changed_date = EXCLUDED.status_changed_date, favorite = EXCLUDED.favorite,
                        group_id = EXCLUDED.group_id, auditors = EXCLUDED.auditors, accomplices = EXCLUDED.accomplices,
                        new_comments_count = EXCLUDED.new_comments_count, "group" = EXCLUDED."group",
                        creator = EXCLUDED.creator, responsible = EXCLUDED.responsible,
                        accomplices_data = EXCLUDED.accomplices_data, auditors_data = EXCLUDED.auditors_data,
                        sub_status = EXCLUDED.sub_status
                """, (
                    data.get("id"), data.get("parentId"), data.get("title", ""), data.get("description"),
                    data.get("mark"), data.get("priority", "1"), convert_yn_to_bool(data.get("multitask", "N")),
                    convert_yn_to_bool(data.get("notViewed", "N")), convert_yn_to_bool(data.get("replicate", "N")),
                    data.get("stageId", "0"), data.get("createdBy", "0"), data.get("createdDate"),
                    data.get("responsibleId", "0"), data.get("changedBy", "0"), data.get("changedDate"),
                    status_changed_by, data.get("closedBy"), data.get("closedDate"),
                    data.get("activityDate"), data.get("dateStart"), data.get("deadline"),
                    data.get("startDatePlan"), data.get("endDatePlan"), data.get("guid"), data.get("xmlId"),
                    data.get("commentsCount"), data.get("serviceCommentsCount"),
                    convert_yn_to_bool(data.get("allowChangeDeadline", "N")),
                    convert_yn_to_bool(data.get("allowTimeTracking", "N")),
                    convert_yn_to_bool(data.get("taskControl", "N")),
                    convert_yn_to_bool(data.get("addInReport", "N")),
                    data.get("forkedByTemplateId"), data.get("timeEstimate", "0"), data.get("timeSpentInLogs"),
                    convert_yn_to_bool(data.get("matchWorkTime", "N")), data.get("forumTopicId"),
                    data.get("forumId"), data.get("siteId"), convert_yn_to_bool(data.get("subordinate", "N")),
                    data.get("exchangeModified"), data.get("exchangeId"), data.get("outlookVersion"),
                    data.get("viewedDate"), data.get("sorting"), data.get("durationPlan"),
                    data.get("durationFact"), data.get("durationType", "days"),
                    convert_yn_to_bool(data.get("isMuted", "N")), convert_yn_to_bool(data.get("isPinned", "N")),
                    convert_yn_to_bool(data.get("isPinnedInGroup", "N")), data.get("flowId"),
                    convert_yn_to_bool(data.get("descriptionInBbcode", "N")), data.get("status", "2"),
                    data.get("statusChangedDate"), convert_yn_to_bool(data.get("favorite", "N")),
                    data.get("groupId", "0"), auditors, accomplices, data.get("newCommentsCount", 0),
                    group, creator_id, responsible_id, accomplices_data, auditors_data, data.get("subStatus", "0")
                ))
                conn.commit()
    except Exception as e:
        logger.error(f"Failed to insert task {data.get('id')}: {e}")
        raise

def insert_project(data):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO projects (
                    id, active, subject_id, subject_data, name, description, keywords, closed, visible,
                    opened, project, landing, date_create, date_update, date_activity, image_id, avatar,
                    avatar_types, avatar_type, owner_id, owner_data, number_of_members,
                    number_of_moderators, initiate_perms, project_date_start, project_date_finish,
                    scrum_owner_id, scrum_master_id, scrum_sprint_duration, scrum_task_responsible,
                    tags, actions, user_data, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    active = EXCLUDED.active, subject_id = EXCLUDED.subject_id,
                    subject_data = EXCLUDED.subject_data, name = EXCLUDED.name,
                    description = EXCLUDED.description, keywords = EXCLUDED.keywords,
                    closed = EXCLUDED.closed, visible = EXCLUDED.visible, opened = EXCLUDED.opened,
                    project = EXCLUDED.project, landing = EXCLUDED.landing,
                    date_create = EXCLUDED.date_create, date_update = EXCLUDED.date_update,
                    date_activity = EXCLUDED.date_activity, image_id = EXCLUDED.image_id,
                    avatar = EXCLUDED.avatar, avatar_types = EXCLUDED.avatar_types,
                    avatar_type = EXCLUDED.avatar_type, owner_id = EXCLUDED.owner_id,
                    owner_data = EXCLUDED.owner_data, number_of_members = EXCLUDED.number_of_members,
                    number_of_moderators = EXCLUDED.number_of_moderators,
                    initiate_perms = EXCLUDED.initiate_perms,
                    project_date_start = EXCLUDED.project_date_start,
                    project_date_finish = EXCLUDED.project_date_finish,
                    scrum_owner_id = EXCLUDED.scrum_owner_id, scrum_master_id = EXCLUDED.scrum_master_id,
                    scrum_sprint_duration = EXCLUDED.scrum_sprint_duration,
                    scrum_task_responsible = EXCLUDED.scrum_task_responsible, tags = EXCLUDED.tags,
                    actions = EXCLUDED.actions, user_data = EXCLUDED.user_data, updated_at = NOW()
            """, (
                data["ID"], data.get("ACTIVE"), data["SUBJECT_ID"], json.dumps(data.get("SUBJECT_DATA", {})),
                data["NAME"], data.get("DESCRIPTION"), data.get("KEYWORDS"), data.get("CLOSED"),
                data.get("VISIBLE"), data.get("OPENED"), data.get("PROJECT"), data.get("LANDING"),
                data.get("DATE_CREATE"), data.get("DATE_UPDATE"), data.get("DATE_ACTIVITY"),
                data.get("IMAGE_ID"), data.get("AVATAR"), json.dumps(data.get("AVATAR_TYPES", {})),
                data.get("AVATAR_TYPE"), data.get("OWNER_ID"), json.dumps(data.get("OWNER_DATA", {})),
                data.get("NUMBER_OF_MEMBERS"), data.get("NUMBER_OF_MODERATORS"), data["INITIATE_PERMS"],
                data.get("PROJECT_DATE_START"), data.get("PROJECT_DATE_FINISH"), data.get("SCRUM_OWNER_ID"),
                data.get("SCRUM_MASTER_ID"), data.get("SCRUM_SPRINT_DURATION"),
                data.get("SCRUM_TASK_RESPONSIBLE"), data.get("TAGS"), json.dumps(data.get("ACTIONS", {})),
                json.dumps(data.get("USER_DATA", {}))
            ))
            conn.commit()

def init_db():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS deals (
                        id VARCHAR PRIMARY KEY,
                        title VARCHAR,
                        amount FLOAT,
                        status VARCHAR,
                        updated_at TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY,
                        parent_id INTEGER,
                        title TEXT NOT NULL,
                        description TEXT,
                        mark TEXT,
                        priority INTEGER NOT NULL DEFAULT 1,
                        multitask BOOLEAN NOT NULL DEFAULT FALSE,
                        not_viewed BOOLEAN NOT NULL DEFAULT FALSE,
                        replicate BOOLEAN NOT NULL DEFAULT FALSE,
                        stage_id INTEGER NOT NULL DEFAULT 0,
                        created_by INTEGER NOT NULL DEFAULT 0,
                        created_date TIMESTAMP WITH TIME ZONE,
                        responsible_id INTEGER NOT NULL DEFAULT 0,
                        changed_by INTEGER NOT NULL DEFAULT 0,
                        changed_date TIMESTAMP WITH TIME ZONE,
                        status_changed_by INTEGER,
                        closed_by INTEGER,
                        closed_date TIMESTAMP WITH TIME ZONE,
                        activity_date TIMESTAMP WITH TIME ZONE,
                        date_start TIMESTAMP WITH TIME ZONE,
                        deadline TIMESTAMP WITH TIME ZONE,
                        start_date_plan TIMESTAMP WITH TIME ZONE,
                        end_date_plan TIMESTAMP WITH TIME ZONE,
                        guid TEXT,
                        xml_id TEXT,
                        comments_count INTEGER,
                        service_comments_count INTEGER,
                        allow_change_deadline BOOLEAN NOT NULL DEFAULT FALSE,
                        allow_time_tracking BOOLEAN NOT NULL DEFAULT FALSE,
                        task_control BOOLEAN NOT NULL DEFAULT FALSE,
                        add_in_report BOOLEAN NOT NULL DEFAULT FALSE,
                        forked_by_template_id INTEGER,
                        time_estimate INTEGER NOT NULL DEFAULT 0,
                        time_spent_in_logs INTEGER,
                        match_work_time BOOLEAN NOT NULL DEFAULT FALSE,
                        forum_topic_id INTEGER,
                        forum_id INTEGER,
                        site_id TEXT,
                        subordinate BOOLEAN NOT NULL DEFAULT FALSE,
                        exchange_modified TIMESTAMP WITH TIME ZONE,
                        exchange_id INTEGER,
                        outlook_version INTEGER,
                        viewed_date TIMESTAMP WITH TIME ZONE,
                        sorting DOUBLE PRECISION,
                        duration_plan INTEGER,
                        duration_fact INTEGER,
                        duration_type TEXT NOT NULL DEFAULT 'days',
                        is_muted BOOLEAN NOT NULL DEFAULT FALSE,
                        is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
                        is_pinned_in_group BOOLEAN NOT NULL DEFAULT FALSE,
                        flow_id INTEGER,
                        description_in_bbcode BOOLEAN NOT NULL DEFAULT FALSE,
                        status INTEGER NOT NULL DEFAULT 2,
                        status_changed_date TIMESTAMP WITH TIME ZONE,
                        favorite BOOLEAN NOT NULL DEFAULT FALSE,
                        group_id INTEGER NOT NULL DEFAULT 0,
                        auditors JSONB NOT NULL DEFAULT '[]'::jsonb,
                        accomplices JSONB NOT NULL DEFAULT '[]'::jsonb,
                        new_comments_count INTEGER NOT NULL DEFAULT 0,
                        "group" JSONB NOT NULL DEFAULT '[]'::jsonb,
                        creator INTEGER NOT NULL DEFAULT 0,
                        responsible INTEGER NOT NULL DEFAULT 0,
                        accomplices_data JSONB NOT NULL DEFAULT '[]'::jsonb,
                        auditors_data JSONB NOT NULL DEFAULT '[]'::jsonb,
                        sub_status INTEGER NOT NULL DEFAULT 0
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id VARCHAR PRIMARY KEY,
                        active VARCHAR CHECK (active IN ('Y', 'N')),
                        subject_id VARCHAR NOT NULL,
                        subject_data JSONB,
                        name VARCHAR NOT NULL,
                        description TEXT,
                        keywords TEXT,
                        closed VARCHAR CHECK (closed IN ('Y', 'N')),
                        visible VARCHAR CHECK (visible IN ('Y', 'N')),
                        opened VARCHAR CHECK (opened IN ('Y', 'N')),
                        project VARCHAR CHECK (project IN ('Y', 'N')) DEFAULT 'N',
                        landing VARCHAR CHECK (landing IN ('Y', 'N')),
                        date_create TIMESTAMP,
                        date_update TIMESTAMP,
                        date_activity TIMESTAMP,
                        image_id VARCHAR,
                        avatar VARCHAR,
                        avatar_types JSONB,
                        avatar_type VARCHAR CHECK (avatar_type IN ('folder', 'checks', 'pie', 'bag', 'members')),
                        owner_id VARCHAR,
                        owner_data JSONB,
                        number_of_members INTEGER,
                        number_of_moderators INTEGER,
                        initiate_perms VARCHAR CHECK (initiate_perms IN ('A', 'E', 'K')) NOT NULL,
                        project_date_start TIMESTAMP,
                        project_date_finish TIMESTAMP,
                        scrum_owner_id VARCHAR,
                        scrum_master_id VARCHAR,
                        scrum_sprint_duration INTEGER,
                        scrum_task_responsible VARCHAR CHECK (scrum_task_responsible IN ('A', 'M')),
                        tags TEXT,
                        actions JSONB,
                        user_data JSONB,
                        updated_at TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

init_db()

@app.route("/status", methods=["GET"])
def status():
    bitrix_status = check_bitrix_status()
    return jsonify({"backend": {"status": "running"}, "bitrix24": bitrix_status}), 200

@app.route("/sync_counts", methods=["GET"])
def sync_counts():
    return jsonify({
        "deals": {"bitrix": get_count_from_bitrix("deals"), "db": get_count_from_db("deals")},
        "tasks": {"bitrix": get_count_from_bitrix("tasks"), "db": get_count_from_db("tasks")},
        "projects": {"bitrix": get_count_from_bitrix("projects"), "db": get_count_from_db("projects")}
    }), 200

@app.route("/sync_status", methods=["GET"])
def get_sync_status():
    return jsonify(sync_status), 200

@app.route("/sync/<entity>", methods=["POST"])
def start_sync(entity):
    if entity not in sync_status:
        return jsonify({"status": "error", "message": "Invalid entity"}), 400
    if sync_status[entity]["running"]:
        return jsonify({"status": "error", "message": "Sync already running"}), 400
    threading.Thread(target=sync_entity, args=(entity,), daemon=True).start()
    return jsonify({"status": "success", "message": f"Syncing {entity} started"}), 200

@app.route("/stop_sync/<entity>", methods=["POST"])
def stop_sync(entity):
    if entity not in sync_status:
        return jsonify({"status": "error", "message": "Invalid entity"}), 400
    if not sync_status[entity]["running"]:
        return jsonify({"status": "error", "message": "No sync running for this entity"}), 400
    sync_status[entity]["stop_requested"] = True
    return jsonify({"status": "success", "message": f"Stopping sync for {entity} requested"}), 200

@app.route("/clear/<entity>", methods=["POST"])
def clear_entity(entity):
    if entity not in sync_status:
        return jsonify({"status": "error", "message": "Invalid entity"}), 400
    if sync_status[entity]["running"]:
        return jsonify({"status": "error", "message": "Sync is running, cannot clear"}), 400
    threading.Thread(target=clear_table, args=(entity,), daemon=True).start()
    return jsonify({"status": "success", "message": f"Clearing {entity} started"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)