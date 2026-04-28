"""
=============================================================================
  LLM Proxy 模型配置管理工具 (Admin CLI)
=============================================================================
  功能：对以下三张模型配置表进行增删改查：
    1. model_configs        — 文本模型（价格按 1K input/output token 计费）
    2. image_model_configs  — 图片模型（含分辨率子表，按每张图片计费）
    3. video_model_configs  — 视频模型（含分辨率子表，按每秒计费）

  使用方式：
    python admin_model_manager.py              # 使用默认配置文件 admin_config.yaml
    python admin_model_manager.py my_conf.yaml # 使用指定的配置文件

  依赖安装：
    pip install sqlalchemy pymysql pyyaml
=============================================================================
"""

import sys
import os
from datetime import datetime
from pathlib import Path
from decimal import Decimal

import yaml
from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    String,
    DECIMAL,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import (
    sessionmaker,
    Session,
    relationship,
    declarative_base,
    joinedload,
)

# =============================================================================
#  模型定义（与 llm-proxy/models/ 中的定义一致）
# =============================================================================

Base = declarative_base()


class ModelConfig(Base):
    """文本模型配置表"""
    __tablename__ = "model_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False, unique=True)
    price_per_1k_input = Column(DECIMAL(10, 6), nullable=False)
    price_per_1k_output = Column(DECIMAL(10, 6), nullable=False)
    is_enabled = Column(BigInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImageModelConfig(Base):
    """图片模型配置表"""
    __tablename__ = "image_model_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False, unique=True)
    is_enabled = Column(BigInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resolutions = relationship(
        "ImageResolutionPrice",
        back_populates="model",
        cascade="all, delete-orphan",
    )


class ImageResolutionPrice(Base):
    """图片模型分辨率价格表"""
    __tablename__ = "image_resolution_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(BigInteger, ForeignKey("image_model_configs.id"), nullable=False)
    resolution = Column(String(20), nullable=False)
    price_per_image = Column(DECIMAL(10, 6), nullable=False)
    is_default = Column(BigInteger, default=0)

    model = relationship("ImageModelConfig", back_populates="resolutions")

    __table_args__ = (
        UniqueConstraint("model_id", "resolution", name="uq_model_resolution"),
    )


class VideoModelConfig(Base):
    """视频模型配置表"""
    __tablename__ = "video_model_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False, unique=True)
    is_enabled = Column(BigInteger, default=1)
    default_duration = Column(BigInteger, default=5, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resolutions = relationship(
        "VideoResolutionPrice",
        back_populates="model",
        cascade="all, delete-orphan",
    )


class VideoResolutionPrice(Base):
    """视频模型分辨率价格表"""
    __tablename__ = "video_resolution_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(BigInteger, ForeignKey("video_model_configs.id"), nullable=False)
    resolution = Column(String(20), nullable=False)
    price_per_second = Column(DECIMAL(10, 6), nullable=False)
    is_default = Column(BigInteger, default=0)

    model = relationship("VideoModelConfig", back_populates="resolutions")

    __table_args__ = (
        UniqueConstraint("model_id", "resolution", name="uq_model_resolution"),
    )


# =============================================================================
#  配置加载
# =============================================================================

def load_config(config_path: str = "admin_config.yaml") -> dict:
    """从 YAML 文件加载数据库配置"""
    path = Path(config_path)
    if not path.exists():
        print(f"❌ 配置文件不存在: {path.resolve()}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_db_session(config: dict) -> Session:
    """根据配置创建数据库会话"""
    db = config["database"]
    url = f"mysql+pymysql://{db['username']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
    engine = create_engine(url, pool_pre_ping=True, echo=False)
    Base.metadata.create_all(bind=engine)  # 确保表存在
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# =============================================================================
#  工具函数
# =============================================================================

def clear_screen():
    """清屏"""
    os.system("cls" if os.name == "nt" else "clear")


def safe_input(prompt: str, allow_empty: bool = False) -> str:
    """安全输入，允许退出"""
    value = input(prompt).strip()
    if value.lower() in ("q", "quit", "exit"):
        return None
    if not allow_empty and not value:
        print("  ⚠️  输入不能为空，请重新输入（输入 q 退出）")
        return safe_input(prompt, allow_empty)
    return value


def input_decimal(prompt: str) -> Decimal | None:
    """输入 Decimal 类型数值"""
    raw = input(prompt).strip()
    if raw.lower() in ("q", "quit", "exit"):
        return None
    try:
        return Decimal(raw)
    except Exception:
        print("  ⚠️  请输入有效的数字（如 0.01）")
        return input_decimal(prompt)


def input_int(prompt: str, default: int = None) -> int | None:
    """输入整数"""
    hint = f" (默认 {default})" if default is not None else ""
    raw = input(f"{prompt}{hint}: ").strip()
    if raw.lower() in ("q", "quit", "exit"):
        return None
    if not raw and default is not None:
        return default
    try:
        return int(raw)
    except ValueError:
        print("  ⚠️  请输入有效的整数")
        return input_int(prompt, default)


def input_yes_no(prompt: str) -> bool | None:
    """输入 y/n"""
    raw = input(f"{prompt} (y/n): ").strip().lower()
    if raw in ("q", "quit", "exit"):
        return None
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    print("  ⚠️  请输入 y 或 n")
    return input_yes_no(prompt)


def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")
    else:
        print(f"{'─' * 60}")


def print_model_header():
    """打印表头"""
    print(f"{'ID':<6} {'名称':<30} {'启用':<6} {'创建时间':<22}")
    print(f"{'─' * 70}")


def press_enter():
    """按回车继续"""
    input("\n按 Enter 返回主菜单...")


# =============================================================================
#  1. 文本模型管理 (model_configs)
# =============================================================================

def text_model_list(db: Session):
    """列出所有文本模型"""
    models = db.query(ModelConfig).order_by(ModelConfig.id).all()
    clear_screen()
    print_separator("文本模型列表 (model_configs)")
    if not models:
        print("  (暂无数据)")
    else:
        print(f"{'ID':<6} {'模型名称':<30} {'启用':<6} {'1K Input($)':<14} {'1K Output($)':<14}")
        print(f"{'─' * 75}")
        for m in models:
            enabled = "✓" if m.is_enabled == 1 else "✗"
            print(
                f"{m.id:<6} {m.model_name:<30} {enabled:<6} "
                f"{float(m.price_per_1k_input):<14.6f} {float(m.price_per_1k_output):<14.6f}"
            )
    press_enter()


def text_model_detail(db: Session):
    """查看单个文本模型详情"""
    name = safe_input("请输入模型名称: ")
    if name is None:
        return
    m = db.query(ModelConfig).filter(ModelConfig.model_name == name).first()
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return
    print_separator("模型详情")
    print(f"  ID:              {m.id}")
    print(f"  名称:            {m.model_name}")
    print(f"  启用状态:        {'✓ 已启用' if m.is_enabled == 1 else '✗ 已禁用'}")
    print(f"  1K Input 价格:   {float(m.price_per_1k_input):.6f}")
    print(f"  1K Output 价格:  {float(m.price_per_1k_output):.6f}")
    print(f"  创建时间:        {m.created_at}")
    print(f"  更新时间:        {m.updated_at}")
    press_enter()


def text_model_add(db: Session):
    """新增文本模型"""
    clear_screen()
    print_separator("新增文本模型")
    print("  (随时输入 q 取消操作)\n")

    name = safe_input("模型名称: ")
    if name is None:
        return

    existing = db.query(ModelConfig).filter(ModelConfig.model_name == name).first()
    if existing:
        print(f"  ❌ 模型 '{name}' 已存在！")
        press_enter()
        return

    price_in = input_decimal("1K Input 价格 ($): ")
    if price_in is None:
        return
    price_out = input_decimal("1K Output 价格 ($): ")
    if price_out is None:
        return
    enabled = input_int("是否启用 (1=是, 0=否)", default=1)
    if enabled is None:
        return

    model = ModelConfig(
        model_name=name,
        price_per_1k_input=price_in,
        price_per_1k_output=price_out,
        is_enabled=enabled,
    )
    db.add(model)
    db.commit()
    print(f"\n  ✅ 文本模型 '{name}' 添加成功！")
    press_enter()


def text_model_edit(db: Session):
    """编辑文本模型"""
    name = safe_input("请输入要编辑的模型名称: ")
    if name is None:
        return
    m = db.query(ModelConfig).filter(ModelConfig.model_name == name).first()
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return

    print(f"\n  当前配置:")
    print(f"  1K Input 价格:   {float(m.price_per_1k_input):.6f}")
    print(f"  1K Output 价格:  {float(m.price_per_1k_output):.6f}")
    print(f"  启用状态:        {'已启用' if m.is_enabled == 1 else '已禁用'}")
    print("\n  (直接回车保留原值，输入 q 取消)\n")

    new_name = input(f"新模型名称 [{m.model_name}]: ").strip()
    if new_name.lower() in ("q", "quit", "exit"):
        return

    raw_in = input(f"新 1K Input 价格 [{float(m.price_per_1k_input):.6f}]: ").strip()
    if raw_in.lower() in ("q", "quit", "exit"):
        return

    raw_out = input(f"新 1K Output 价格 [{float(m.price_per_1k_output):.6f}]: ").strip()
    if raw_out.lower() in ("q", "quit", "exit"):
        return

    raw_enabled = input(f"是否启用 (1/0) [{m.is_enabled}]: ").strip()
    if raw_enabled.lower() in ("q", "quit", "exit"):
        return

    if new_name:
        m.model_name = new_name
    if raw_in:
        try:
            m.price_per_1k_input = Decimal(raw_in)
        except Exception:
            print("  ⚠️  价格格式错误，已跳过")
    if raw_out:
        try:
            m.price_per_1k_output = Decimal(raw_out)
        except Exception:
            print("  ⚠️  价格格式错误，已跳过")
    if raw_enabled:
        m.is_enabled = int(raw_enabled)

    m.updated_at = datetime.utcnow()
    db.commit()
    print(f"\n  ✅ 模型 '{m.model_name}' 更新成功！")
    press_enter()


def text_model_delete(db: Session):
    """删除文本模型"""
    name = safe_input("请输入要删除的模型名称: ")
    if name is None:
        return
    m = db.query(ModelConfig).filter(ModelConfig.model_name == name).first()
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return

    confirm = input_yes_no(f"  确认删除模型 '{name}'？此操作不可撤销！")
    if confirm is None:
        return
    if confirm:
        db.delete(m)
        db.commit()
        print(f"  ✅ 模型 '{name}' 已删除！")
    else:
        print("  已取消。")
    press_enter()


# =============================================================================
#  2. 图片模型管理 (image_model_configs + image_resolution_prices)
# =============================================================================

def image_model_list(db: Session):
    """列出所有图片模型"""
    models = (
        db.query(ImageModelConfig)
        .options(joinedload(ImageModelConfig.resolutions))
        .order_by(ImageModelConfig.id)
        .all()
    )
    clear_screen()
    print_separator("图片模型列表 (image_model_configs)")
    if not models:
        print("  (暂无数据)")
    else:
        for m in models:
            enabled = "✓" if m.is_enabled == 1 else "✗"
            print(f"\n  [{enabled}] {m.model_name}  (ID: {m.id})")
            if m.resolutions:
                print(f"    {'分辨率':<14} {'每张单价($)':<14} {'默认'}")
                print(f"    {'─' * 36}")
                for r in m.resolutions:
                    default_mark = "★" if r.is_default == 1 else ""
                    print(
                        f"    {r.resolution:<14} {float(r.price_per_image):<14.6f} {default_mark}"
                    )
            else:
                print("    (暂无分辨率配置)")
    press_enter()


def image_model_add(db: Session):
    """新增图片模型"""
    clear_screen()
    print_separator("新增图片模型")
    print("  (随时输入 q 取消操作)\n")

    name = safe_input("模型名称: ")
    if name is None:
        return

    existing = (
        db.query(ImageModelConfig).filter(ImageModelConfig.model_name == name).first()
    )
    if existing:
        print(f"  ❌ 模型 '{name}' 已存在！")
        press_enter()
        return

    enabled = input_int("是否启用 (1=是, 0=否)", default=1)
    if enabled is None:
        return

    model = ImageModelConfig(model_name=name, is_enabled=enabled)
    db.add(model)
    db.flush()  # 获取 model.id

    print("\n  现在添加分辨率价格配置:")
    has_default = False
    while True:
        print()
        res = safe_input("  分辨率 (如 256x256, 512x512, 1024x1024，空行结束): ", allow_empty=True)
        if res is None:
            db.rollback()
            return
        if not res:
            if not model.resolutions:
                print("  ⚠️  至少需要添加一个分辨率！")
                continue
            break

        price = input_decimal(f"  每张单价 ($) [{res}]: ")
        if price is None:
            db.rollback()
            return

        is_def = False
        if not has_default:
            ans = input_yes_no("  设为默认分辨率？")
            if ans is None:
                db.rollback()
                return
            if ans:
                is_def = True
                has_default = True

        rp = ImageResolutionPrice(
            model_id=model.id,
            resolution=res,
            price_per_image=price,
            is_default=1 if is_def else 0,
        )
        model.resolutions.append(rp)
        print(f"  ✅ 分辨率 '{res}' 已添加")

    db.commit()
    print(f"\n  ✅ 图片模型 '{name}' 及 {len(model.resolutions)} 个分辨率配置添加成功！")
    press_enter()


def image_model_edit(db: Session):
    """编辑图片模型"""
    name = safe_input("请输入要编辑的模型名称: ")
    if name is None:
        return
    m = (
        db.query(ImageModelConfig)
        .options(joinedload(ImageModelConfig.resolutions))
        .filter(ImageModelConfig.model_name == name)
        .first()
    )
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return

    print(f"\n  当前配置:")
    print(f"  启用状态: {'已启用' if m.is_enabled == 1 else '已禁用'}")
    print(f"  分辨率配置:")
    for r in m.resolutions:
        default_mark = " ★默认" if r.is_default == 1 else ""
        print(f"    - {r.resolution}: ${float(r.price_per_image):.6f}/张{default_mark}")

    print("\n  (直接回车保留原值，输入 q 取消)\n")

    new_name = input(f"新模型名称 [{m.model_name}]: ").strip()
    if new_name.lower() in ("q", "quit", "exit"):
        return

    raw_enabled = input(f"是否启用 (1/0) [{m.is_enabled}]: ").strip()
    if raw_enabled.lower() in ("q", "quit", "exit"):
        return

    if new_name:
        m.model_name = new_name
    if raw_enabled:
        m.is_enabled = int(raw_enabled)

    # 编辑分辨率
    edit_res = input_yes_no("是否编辑分辨率配置？")
    if edit_res is None:
        return
    if edit_res:
        _edit_image_resolutions(db, m)

    m.updated_at = datetime.utcnow()
    db.commit()
    print(f"\n  ✅ 图片模型 '{m.model_name}' 更新成功！")
    press_enter()


def _edit_image_resolutions(db: Session, model: ImageModelConfig):
    """交互式编辑图片模型的分辨率配置"""
    while True:
        clear_screen()
        print_separator(f"编辑分辨率 - {model.model_name}")
        print("  当前分辨率配置:")
        for i, r in enumerate(model.resolutions, 1):
            default_mark = " ★默认" if r.is_default == 1 else ""
            print(f"    [{i}] {r.resolution}: ${float(r.price_per_image):.6f}/张{default_mark}")
        print("\n  操作: (A)新增  (D 序号)删除  (E 序号)编辑  (空)完成")

        cmd = input("\n  请输入操作: ").strip()
        if cmd.lower() in ("q", "quit", "exit"):
            return
        if not cmd:
            break

        parts = cmd.split(maxsplit=1)
        action = parts[0].upper()

        if action == "A":
            res = safe_input("  分辨率: ")
            if res is None:
                continue
            price = input_decimal("  每张单价 ($): ")
            if price is None:
                continue
            is_def = 0
            if not any(r.is_default == 1 for r in model.resolutions):
                ans = input_yes_no("  设为默认分辨率？")
                if ans is None:
                    continue
                if ans:
                    is_def = 1
            rp = ImageResolutionPrice(
                model_id=model.id,
                resolution=res,
                price_per_image=price,
                is_default=is_def,
            )
            model.resolutions.append(rp)
            db.flush()
            print("  ✅ 已添加")

        elif action == "D":
            if len(parts) < 2:
                print("  ⚠️  用法: D 序号")
                press_enter()
                continue
            try:
                idx = int(parts[1]) - 1
                target = model.resolutions[idx]
                db.delete(target)
                db.flush()
                print(f"  ✅ 分辨率 '{target.resolution}' 已删除")
            except (IndexError, ValueError):
                print("  ⚠️  无效的序号")

        elif action == "E":
            if len(parts) < 2:
                print("  ⚠️  用法: E 序号")
                press_enter()
                continue
            try:
                idx = int(parts[1]) - 1
                target = model.resolutions[idx]
                new_res = input(f"  新分辨率 [{target.resolution}]: ").strip()
                if new_res.lower() in ("q", "quit", "exit"):
                    continue
                new_price = input_decimal(f"  新单价 [{float(target.price_per_image):.6f}]: ")
                if new_price is None:
                    continue
                is_def = input_int(f"  是否默认 (1/0) [{target.is_default}]: ")
                if is_def is None:
                    continue
                if new_res:
                    target.resolution = new_res
                target.price_per_image = new_price
                target.is_default = is_def
                db.flush()
                print("  ✅ 已更新")
            except (IndexError, ValueError):
                print("  ⚠️  无效的序号")

        else:
            print("  ⚠️  未知操作")
        press_enter()


def image_model_delete(db: Session):
    """删除图片模型"""
    name = safe_input("请输入要删除的模型名称: ")
    if name is None:
        return
    m = (
        db.query(ImageModelConfig)
        .options(joinedload(ImageModelConfig.resolutions))
        .filter(ImageModelConfig.model_name == name)
        .first()
    )
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return

    print(f"\n  将删除模型 '{name}' 及其 {len(m.resolutions)} 个分辨率配置")
    confirm = input_yes_no("  确认删除？此操作不可撤销！")
    if confirm is None:
        return
    if confirm:
        db.delete(m)
        db.commit()
        print(f"  ✅ 图片模型 '{name}' 及关联分辨率已删除！")
    else:
        print("  已取消。")
    press_enter()


# =============================================================================
#  3. 视频模型管理 (video_model_configs + video_resolution_prices)
# =============================================================================

def video_model_list(db: Session):
    """列出所有视频模型"""
    models = (
        db.query(VideoModelConfig)
        .options(joinedload(VideoModelConfig.resolutions))
        .order_by(VideoModelConfig.id)
        .all()
    )
    clear_screen()
    print_separator("视频模型列表 (video_model_configs)")
    if not models:
        print("  (暂无数据)")
    else:
        for m in models:
            enabled = "✓" if m.is_enabled == 1 else "✗"
            print(
                f"\n  [{enabled}] {m.model_name}  (ID: {m.id})  "
                f"默认时长: {m.default_duration}s"
            )
            if m.resolutions:
                print(f"    {'分辨率':<12} {'每秒单价($)':<14} {'默认'}")
                print(f"    {'─' * 32}")
                for r in m.resolutions:
                    default_mark = "★" if r.is_default == 1 else ""
                    print(
                        f"    {r.resolution:<12} {float(r.price_per_second):<14.6f} {default_mark}"
                    )
            else:
                print("    (暂无分辨率配置)")
    press_enter()


def video_model_add(db: Session):
    """新增视频模型"""
    clear_screen()
    print_separator("新增视频模型")
    print("  (随时输入 q 取消操作)\n")

    name = safe_input("模型名称: ")
    if name is None:
        return

    existing = (
        db.query(VideoModelConfig).filter(VideoModelConfig.model_name == name).first()
    )
    if existing:
        print(f"  ❌ 模型 '{name}' 已存在！")
        press_enter()
        return

    duration = input_int("默认生成时长 (秒)", default=5)
    if duration is None:
        return
    enabled = input_int("是否启用 (1=是, 0=否)", default=1)
    if enabled is None:
        return

    model = VideoModelConfig(
        model_name=name,
        default_duration=duration,
        is_enabled=enabled,
    )
    db.add(model)
    db.flush()

    print("\n  现在添加分辨率价格配置:")
    has_default = False
    while True:
        print()
        res = safe_input("  分辨率 (如 720p, 1080p, 4k，空行结束): ", allow_empty=True)
        if res is None:
            db.rollback()
            return
        if not res:
            if not model.resolutions:
                print("  ⚠️  至少需要添加一个分辨率！")
                continue
            break

        price = input_decimal(f"  每秒单价 ($) [{res}]: ")
        if price is None:
            db.rollback()
            return

        is_def = False
        if not has_default:
            ans = input_yes_no("  设为默认分辨率？")
            if ans is None:
                db.rollback()
                return
            if ans:
                is_def = True
                has_default = True

        rp = VideoResolutionPrice(
            model_id=model.id,
            resolution=res,
            price_per_second=price,
            is_default=1 if is_def else 0,
        )
        model.resolutions.append(rp)
        print(f"  ✅ 分辨率 '{res}' 已添加")

    db.commit()
    print(f"\n  ✅ 视频模型 '{name}' 及 {len(model.resolutions)} 个分辨率配置添加成功！")
    press_enter()


def video_model_edit(db: Session):
    """编辑视频模型"""
    name = safe_input("请输入要编辑的模型名称: ")
    if name is None:
        return
    m = (
        db.query(VideoModelConfig)
        .options(joinedload(VideoModelConfig.resolutions))
        .filter(VideoModelConfig.model_name == name)
        .first()
    )
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return

    print(f"\n  当前配置:")
    print(f"  默认时长:   {m.default_duration}s")
    print(f"  启用状态:   {'已启用' if m.is_enabled == 1 else '已禁用'}")
    print(f"  分辨率配置:")
    for r in m.resolutions:
        default_mark = " ★默认" if r.is_default == 1 else ""
        print(f"    - {r.resolution}: ${float(r.price_per_second):.6f}/秒{default_mark}")

    print("\n  (直接回车保留原值，输入 q 取消)\n")

    new_name = input(f"新模型名称 [{m.model_name}]: ").strip()
    if new_name.lower() in ("q", "quit", "exit"):
        return

    raw_dur = input(f"默认时长 (秒) [{m.default_duration}]: ").strip()
    if raw_dur.lower() in ("q", "quit", "exit"):
        return

    raw_enabled = input(f"是否启用 (1/0) [{m.is_enabled}]: ").strip()
    if raw_enabled.lower() in ("q", "quit", "exit"):
        return

    if new_name:
        m.model_name = new_name
    if raw_dur:
        try:
            m.default_duration = int(raw_dur)
        except ValueError:
            print("  ⚠️  时长格式错误，已跳过")
    if raw_enabled:
        m.is_enabled = int(raw_enabled)

    edit_res = input_yes_no("是否编辑分辨率配置？")
    if edit_res is None:
        return
    if edit_res:
        _edit_video_resolutions(db, m)

    m.updated_at = datetime.utcnow()
    db.commit()
    print(f"\n  ✅ 视频模型 '{m.model_name}' 更新成功！")
    press_enter()


def _edit_video_resolutions(db: Session, model: VideoModelConfig):
    """交互式编辑视频模型的分辨率配置"""
    while True:
        clear_screen()
        print_separator(f"编辑分辨率 - {model.model_name}")
        print("  当前分辨率配置:")
        for i, r in enumerate(model.resolutions, 1):
            default_mark = " ★默认" if r.is_default == 1 else ""
            print(f"    [{i}] {r.resolution}: ${float(r.price_per_second):.6f}/秒{default_mark}")
        print("\n  操作: (A)新增  (D 序号)删除  (E 序号)编辑  (空)完成")

        cmd = input("\n  请输入操作: ").strip()
        if cmd.lower() in ("q", "quit", "exit"):
            return
        if not cmd:
            break

        parts = cmd.split(maxsplit=1)
        action = parts[0].upper()

        if action == "A":
            res = safe_input("  分辨率: ")
            if res is None:
                continue
            price = input_decimal("  每秒单价 ($): ")
            if price is None:
                continue
            is_def = 0
            if not any(r.is_default == 1 for r in model.resolutions):
                ans = input_yes_no("  设为默认分辨率？")
                if ans is None:
                    continue
                if ans:
                    is_def = 1
            rp = VideoResolutionPrice(
                model_id=model.id,
                resolution=res,
                price_per_second=price,
                is_default=is_def,
            )
            model.resolutions.append(rp)
            db.flush()
            print("  ✅ 已添加")

        elif action == "D":
            if len(parts) < 2:
                print("  ⚠️  用法: D 序号")
                press_enter()
                continue
            try:
                idx = int(parts[1]) - 1
                target = model.resolutions[idx]
                db.delete(target)
                db.flush()
                print(f"  ✅ 分辨率 '{target.resolution}' 已删除")
            except (IndexError, ValueError):
                print("  ⚠️  无效的序号")

        elif action == "E":
            if len(parts) < 2:
                print("  ⚠️  用法: E 序号")
                press_enter()
                continue
            try:
                idx = int(parts[1]) - 1
                target = model.resolutions[idx]
                new_res = input(f"  新分辨率 [{target.resolution}]: ").strip()
                if new_res.lower() in ("q", "quit", "exit"):
                    continue
                new_price = input_decimal(f"  新单价 [{float(target.price_per_second):.6f}]: ")
                if new_price is None:
                    continue
                is_def = input_int(f"  是否默认 (1/0) [{target.is_default}]: ")
                if is_def is None:
                    continue
                if new_res:
                    target.resolution = new_res
                target.price_per_second = new_price
                target.is_default = is_def
                db.flush()
                print("  ✅ 已更新")
            except (IndexError, ValueError):
                print("  ⚠️  无效的序号")

        else:
            print("  ⚠️  未知操作")
        press_enter()


def video_model_delete(db: Session):
    """删除视频模型"""
    name = safe_input("请输入要删除的模型名称: ")
    if name is None:
        return
    m = (
        db.query(VideoModelConfig)
        .options(joinedload(VideoModelConfig.resolutions))
        .filter(VideoModelConfig.model_name == name)
        .first()
    )
    if not m:
        print(f"  ❌ 未找到模型: {name}")
        press_enter()
        return

    print(f"\n  将删除模型 '{name}' 及其 {len(m.resolutions)} 个分辨率配置")
    confirm = input_yes_no("  确认删除？此操作不可撤销！")
    if confirm is None:
        return
    if confirm:
        db.delete(m)
        db.commit()
        print(f"  ✅ 视频模型 '{name}' 及关联分辨率已删除！")
    else:
        print("  已取消。")
    press_enter()


# =============================================================================
#  菜单系统
# =============================================================================

def menu_text_model(db: Session):
    """文本模型管理子菜单"""
    while True:
        clear_screen()
        print_separator("📝 文本模型管理 (model_configs)")
        print("  [1] 查看所有模型")
        print("  [2] 查看模型详情")
        print("  [3] 新增模型")
        print("  [4] 编辑模型")
        print("  [5] 删除模型")
        print("  [0] 返回主菜单")
        print(f"{'─' * 60}")

        choice = input("请选择操作: ").strip()
        if choice == "1":
            text_model_list(db)
        elif choice == "2":
            text_model_detail(db)
        elif choice == "3":
            text_model_add(db)
        elif choice == "4":
            text_model_edit(db)
        elif choice == "5":
            text_model_delete(db)
        elif choice == "0":
            break
        else:
            print("  ⚠️  无效选择，请重新输入")


def menu_image_model(db: Session):
    """图片模型管理子菜单"""
    while True:
        clear_screen()
        print_separator("🖼️  图片模型管理 (image_model_configs)")
        print("  [1] 查看所有模型")
        print("  [2] 新增模型（含分辨率）")
        print("  [3] 编辑模型（含分辨率）")
        print("  [4] 删除模型（含分辨率）")
        print("  [0] 返回主菜单")
        print(f"{'─' * 60}")

        choice = input("请选择操作: ").strip()
        if choice == "1":
            image_model_list(db)
        elif choice == "2":
            image_model_add(db)
        elif choice == "3":
            image_model_edit(db)
        elif choice == "4":
            image_model_delete(db)
        elif choice == "0":
            break
        else:
            print("  ⚠️  无效选择，请重新输入")


def menu_video_model(db: Session):
    """视频模型管理子菜单"""
    while True:
        clear_screen()
        print_separator("🎬 视频模型管理 (video_model_configs)")
        print("  [1] 查看所有模型")
        print("  [2] 新增模型（含分辨率）")
        print("  [3] 编辑模型（含分辨率）")
        print("  [4] 删除模型（含分辨率）")
        print("  [0] 返回主菜单")
        print(f"{'─' * 60}")

        choice = input("请选择操作: ").strip()
        if choice == "1":
            video_model_list(db)
        elif choice == "2":
            video_model_add(db)
        elif choice == "3":
            video_model_edit(db)
        elif choice == "4":
            video_model_delete(db)
        elif choice == "0":
            break
        else:
            print("  ⚠️  无效选择，请重新输入")


def main_menu(db: Session):
    """主菜单"""
    while True:
        clear_screen()
        print_separator("⚙️  LLM Proxy - 模型配置管理工具")
        print("  数据库: "
              f"{db.get_bind().url.host}:{db.get_bind().url.port}/{db.get_bind().url.database}")
        print(f"{'=' * 60}")
        print("  [1] 文本模型管理   (model_configs)")
        print("  [2] 图片模型管理   (image_model_configs)")
        print("  [3] 视频模型管理   (video_model_configs)")
        print("  [0] 退出")
        print(f"{'─' * 60}")

        choice = input("请选择模块: ").strip()
        if choice == "1":
            menu_text_model(db)
        elif choice == "2":
            menu_image_model(db)
        elif choice == "3":
            menu_video_model(db)
        elif choice == "0":
            print("\n  再见！")
            break
        else:
            print("  ⚠️  无效选择，请重新输入")


# =============================================================================
#  入口
# =============================================================================

if __name__ == "__main__":
    # 确定配置文件路径
    config_path = sys.argv[1] if len(sys.argv) > 1 else "admin_config.yaml"

    # 如果传了相对路径，相对于脚本所在目录解析
    if not os.path.isabs(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, config_path)

    print(f"📄 使用配置文件: {config_path}")
    config = load_config(config_path)

    try:
        db = create_db_session(config)
        db.execute(text("SELECT 1"))  # 测试连接
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)

    try:
        main_menu(db)
    finally:
        db.close()
