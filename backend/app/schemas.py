"""요청 스키마. 길이 제한은 DB 컬럼 의미를 따른다."""
from pydantic import BaseModel, ConfigDict, Field

Name = Field(default="", max_length=50)


class Body(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)


class LoginIn(Body):
    emp_no: str = Field(max_length=100)
    password: str = Field(max_length=200)


class OtpIn(Body):
    code: str = Field(max_length=10)


class RegisterIn(Body):
    last_name: str = Name
    first_name: str = Name
    birth_date: str = Field(default="", max_length=10)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)
    emp_no: str = Field(default="", max_length=50)
    password: str = Field(default="", max_length=200)
    password_confirm: str = Field(default="", max_length=200)


class MenuAccessIn(Body):
    menu_id: str = Field(max_length=20)


class HullIn(Body):
    hull_no: str | None = Field(default=None, max_length=50)
    hull_nm: str | None = Field(default=None, max_length=100)
    ship_type: str | None = Field(default=None, max_length=20)
    hull_status: str | None = Field(default=None, max_length=20)
    owner_nm: str | None = Field(default=None, max_length=100)
    class_society: str | None = Field(default=None, max_length=50)
    length_m: float | None = None
    breadth_m: float | None = None
    depth_m: float | None = None
    dead_weight: float | None = None
    dock_no: str | None = Field(default=None, max_length=50)
    contract_dt: str | None = Field(default=None, max_length=20)
    delivery_dt: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=500)
    use_yn: bool | None = None


class MilestoneItem(Body):
    milestone_cd: str = Field(max_length=20)
    plan_dt: str | None = Field(default=None, max_length=20)
    actual_dt: str | None = Field(default=None, max_length=20)


class MilestonesIn(Body):
    items: list[MilestoneItem]


class BlockIn(Body):
    block_cd: str | None = Field(default=None, max_length=20)
    block_nm: str | None = Field(default=None, max_length=100)
    block_type: str | None = Field(default=None, max_length=20)
    weight_ton: float | None = None


class PlanIn(Body):
    block_id: int | None = None
    proc_cd: str | None = Field(default=None, max_length=20)
    plan_start_dt: str | None = Field(default=None, max_length=20)
    plan_end_dt: str | None = Field(default=None, max_length=20)
    manager_emp_no: str | None = Field(default=None, max_length=50)
    remark: str | None = Field(default=None, max_length=1000)
    pred_plan_ids: list[int] | None = None
    confirm_late_preds: bool = False


class PredecessorsIn(Body):
    pred_plan_ids: list[int]
    confirm_late_preds: bool = False


class PlanLinkIn(Body):
    drawing_id: int
    required: bool = True


class ProgressIn(Body):
    progress_rate: float | None = None
    man_hour: float | None = None
    worker_cnt: int | None = None
    worker_emp_no: str | None = Field(default=None, max_length=50)
    remark: str | None = Field(default=None, max_length=1000)


class DrawingIn(Body):
    drawing_no: str | None = Field(default=None, max_length=50)
    drawing_nm: str | None = Field(default=None, max_length=200)
    hull_no: str | None = Field(default=None, max_length=50)
    block_id: int | None = None
    discipline: str | None = Field(default=None, max_length=20)
    designer_emp_no: str | None = Field(default=None, max_length=50)


class RevisionIn(Body):
    change_desc: str = Field(default="", max_length=1000)


class ApprovalRequestIn(Body):
    reviewer_emp_no: str | None = Field(default=None, max_length=50)
    approver_emp_no: str | None = Field(default=None, max_length=50)


class DrawingPlanIn(Body):
    plan_id: int
    required: bool = True


class DecisionIn(Body):
    result: str = Field(default="", max_length=20)
    comment: str | None = Field(default=None, max_length=1000)


class UserCreateIn(RegisterIn):
    password_confirm: str | None = Field(default=None, max_length=200)
    status: str = Field(default="approved", max_length=20)
    groups: list[str] = []
    totp_enabled: bool = False


class UserUpdateIn(Body):
    emp_no: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    first_name: str | None = Field(default=None, max_length=50)
    birth_date: str | None = Field(default=None, max_length=10)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=254)
    password: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, max_length=20)
    groups: list[str] | None = None
    totp_enabled: bool | None = None


class ApproveIn(Body):
    groups: list[str] = []
