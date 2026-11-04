from app.services import rules


def add_plan(conn, hull, proc="CUT", start="2026-11-01", end="2026-11-10", rate=0, actual=None):
    return conn.execute(
        "INSERT INTO TB_PRC_Plan (HullNo, ProcCd, PlanStartDt, PlanEndDt, ProgressRate, ActualStartDt) VALUES (?,?,?,?,?,?)",
        (hull, proc, start, end, rate, actual),
    ).lastrowid


def status(conn, plan_id):
    return conn.execute("SELECT PlanStatus FROM TB_PRC_Plan WHERE PlanId=?", (plan_id,)).fetchone()[0]


def test_weighted_rounds_half_up():
    assert rules.weighted(1, 2) == 1
    assert rules.weighted(5, 2) == 3


def test_status_matrix(conn):
    done = add_plan(conn, "8004", rate=100)
    work = add_plan(conn, "8004", rate=10)
    work2 = add_plan(conn, "8004", actual="2026-10-01")
    delay = add_plan(conn, "8004", rate=10, end="2026-10-18", start="2026-10-01")
    delay2 = add_plan(conn, "8004", end="2026-10-18", start="2026-10-01")
    today = add_plan(conn, "8004", end="2026-10-19", start="2026-10-01", rate=10)
    ready = add_plan(conn, "8004")
    waiting = add_plan(conn, "8004")
    conn.execute("INSERT INTO TB_PRC_PlanDep VALUES (?,?,0)", (ready, done))
    conn.execute("INSERT INTO TB_PRC_PlanDep VALUES (?,?,0)", (waiting, work))
    rules.recalc_hull(conn, "8004")
    got = [status(conn, p) for p in (done, work, work2, delay, delay2, today, ready, waiting)]
    assert got == ["DONE", "WORK", "WORK", "DELAY", "DELAY", "WORK", "READY", "PLAN"]


def test_gate_past_issued_passes_and_approved_blocks(conn):
    plan = add_plan(conn, "8004")
    drawing = conn.execute(
        "INSERT INTO TB_DWG_Drawing (DrawingNo, DrawingNm, HullNo, DwgStatus) VALUES ('T-1','x','8004','APPROVED')"
    ).lastrowid
    conn.execute("INSERT INTO TB_DWG_Revision (DrawingId, RevNo, RevStatus) VALUES (?,0,'APPROVED')", (drawing,))
    conn.execute("INSERT INTO TB_DWG_PlanLink (DrawingId, PlanId) VALUES (?,?)", (drawing, plan))
    rules.recalc_hull(conn, "8004")
    assert status(conn, plan) == "PLAN"
    assert rules.blockers(conn, "l.PlanId = ?", (plan,))[plan] == [
        {"drawing_id": drawing, "drawing_no": "T-1", "dwg_status": "APPROVED"}
    ]
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus='ISSUED' WHERE DrawingId=?", (drawing,))
    conn.execute("INSERT INTO TB_DWG_Revision (DrawingId, RevNo, RevStatus) VALUES (?,1,'DRAFT')", (drawing,))
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='DRAFT' WHERE DrawingId=?", (drawing,))
    rules.recalc_hull(conn, "8004")
    assert status(conn, plan) == "READY"


def test_gate_optional_and_obsolete_ignored(conn):
    plan = add_plan(conn, "8004")
    d1 = conn.execute("INSERT INTO TB_DWG_Drawing (DrawingNo, DrawingNm, HullNo) VALUES ('T-2','x','8004')").lastrowid
    d2 = conn.execute(
        "INSERT INTO TB_DWG_Drawing (DrawingNo, DrawingNm, HullNo, DwgStatus) VALUES ('T-3','x','8004','OBSOLETE')"
    ).lastrowid
    conn.execute("INSERT INTO TB_DWG_PlanLink (DrawingId, PlanId, RequiredYN) VALUES (?,?,0)", (d1, plan))
    conn.execute("INSERT INTO TB_DWG_PlanLink (DrawingId, PlanId, RequiredYN) VALUES (?,?,1)", (d2, plan))
    rules.recalc_hull(conn, "8004")
    assert status(conn, plan) == "READY"


def hull_status(conn, hull):
    return conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo=?", (hull,)).fetchone()[0]


def test_hull_auto_transition(conn):
    conn.execute("UPDATE TB_MST_Hull SET HullStatus='DESIGN' WHERE HullNo='8004'")
    add_plan(conn, "8004", rate=10)
    rules.recalc_hull(conn, "8004")
    assert hull_status(conn, "8004") == "BUILD"
    add_plan(conn, "8004", proc="LAUNCH", rate=100)
    rules.recalc_hull(conn, "8004")
    assert hull_status(conn, "8004") == "LAUNCH"


def test_hull_design_to_launch_in_one_pass(conn):
    conn.execute("UPDATE TB_MST_Hull SET HullStatus='DESIGN' WHERE HullNo='8004'")
    add_plan(conn, "8004", rate=10)
    add_plan(conn, "8004", proc="LAUNCH", rate=100)
    rules.recalc_hull(conn, "8004")
    assert hull_status(conn, "8004") == "LAUNCH"


def test_other_hull_status_unchanged(conn):
    conn.execute("UPDATE TB_MST_Hull SET HullStatus='PLAN' WHERE HullNo='8004'")
    add_plan(conn, "8004", rate=10)
    rules.recalc_hull(conn, "8004")
    assert hull_status(conn, "8004") == "PLAN"
