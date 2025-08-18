from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.all import *
import astrbot.api.message_components as Comp

# 使用相对导入方式导入API模块
from .API.SignIn import create_check_in_card
from .API.virtual_time import VirtualClock

import os
import datetime
import requests
import json
import time
import random
import re

# Jinja2 template that supports CSS
TMPL = '''
<style>
/* inventory class: style for the entire container */
.inventory {
    display: grid; /* Use grid layout */
    grid-template-columns: repeat(5, 360px); /* Define grid layout columns: repeat 5 columns, each with the same width */
    grid-gap: 10px; /* Set spacing between grid cells */
    padding: 10px; /* Set container padding */
    border: 1px solid #ccc; /* Set container border */
    background-color: #f9f9f9; /* Set container background color */
    font-size: 48px; /* Increase default font size for the entire inventory */
}

/* inventory-item class: style for each item slot */
.inventory-item {
    border: 1px solid #ddd; /* Set border for item slot */
    padding: 5px; /* Set padding for item slot */
    text-align: left; /* Set text alignment to left */
    font-size: 36px; /* Set font size inside item slot */
    background-color: #fff; /* Set background color for item slot */
}

/* inventory-item p class: style for paragraphs inside item slots */
.inventory-item p {
    margin: 5px 0; /* Set top and bottom margins for paragraphs, adjust spacing */
}

/* inventory-item strong class: style for bold text inside item slots */
.inventory-item strong {
    font-size: 36px; /* Set font size for bold text */
}
</style>

<div class="inventory">
{% for item in items %}  <!-- Loop through each item in the items list -->
    <div class="inventory-item"> <!-- Each item slot -->
        <p><strong>ID:</strong> {{ item.id }}</p> <!-- Display item ID -->
        <p><strong>UserId:</strong> {{ item.user_id }}</p> <!-- Display item UserId -->
        <p><strong>Item Name:</strong> {{ item.item_name }}</p> <!-- Display item name -->
        <p><strong>Item Count:</strong> {{ item.item_count }}</p> <!-- Display item count -->
        <p><strong>Item Type:</strong> {{ item.item_type }}</p> <!-- Display item type -->
        <p><strong>Item Value:</strong> {{ item.item_value }}</p> <!-- Display item value -->
    </div>
{% endfor %} <!-- End loop -->
</div>
'''

def get_formatted_time():
    """
    获取格式化后的时间字符串，格式为：YYYY-MM-DD HH:MM:SS 星期X
    """
    now = datetime.datetime.now()
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_name = weekday_names[now.weekday()]
    return now.strftime(f"%Y-%m-%d %H:%M:%S {weekday_name}")


def get_one_sentence():
    """
    从 https://api.tangdouz.com/a/one.php?return=json 获取一句一言。
    进行错误处理和重试机制，保证服务的稳定性。
    """
    max_retries = 3
    url = "https://api.tangdouz.com/a/one.php?return=json"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)  # 添加超时时间
            response.raise_for_status()  # 检查 HTTP 状态码
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求 one_sentence 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # 增加重试间隔
            else:
                logger.error(f"获取 one_sentence 失败: {e}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析 one_sentence 失败: {e}")
            return None
    return None


def download_image(user_id, PP_PATH, max_retries=3):
    """
    从给定的 URL 下载图像，并将其保存到指定路径。
    Args:
        user_id: 用户ID，用于构建文件名。
        PP_PATH: 保存图像的目录路径。
        max_retries: 最大重试次数（默认为3）。
    Returns:
        True 如果下载成功，否则返回 False。
    """
    url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    filepath = os.path.join(PP_PATH, f"{user_id}.png")
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=10)  # 添加超时时间
            response.raise_for_status()  # 检查响应状态码，如果不是 200，抛出异常
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):  # 以流式方式写入文件
                    f.write(chunk)
            logger.info(f"用户 {user_id} 的图像下载成功，已保存到 {filepath}")
            return True  # 下载成功，返回 True
        except requests.exceptions.RequestException as e:
            logger.warning(f"用户 {user_id} 的图像下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待 2 秒后重试
            else:
                logger.error(f"用户 {user_id} 下载失败，达到最大重试次数。")
    return False  # 下载失败，返回 False


@register("furryhm", "astrbot_plugin_furry_cg", "小茶馆插件", "1.0.0")
class TeaHousePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 使用框架API获取插件数据目录
        self.PLUGIN_DIR = os.path.dirname(__file__)  # 插件根目录
        self.DATA_DIR = os.path.join(os.getcwd(), 'data')      # 框架数据目录
        # 重构子路径
        self.IMAGE_PATH = os.path.join(self.DATA_DIR, 'sign', 'image')
        self.PP_PATH = os.path.join(self.DATA_DIR, 'sign', 'profile_picture')
        self.BACKGROUND_PATH = os.path.join(self.DATA_DIR, 'sign', 'background')
        self.IMAGE_FOLDER = os.path.join(self.PLUGIN_DIR, "backgrounds")
        self.FONT_PATH = os.path.join(self.PLUGIN_DIR, "font.ttf")
        # 创建目录
        os.makedirs(self.PP_PATH, exist_ok=True)
        os.makedirs(self.IMAGE_PATH, exist_ok=True)
        os.makedirs(self.BACKGROUND_PATH, exist_ok=True)
        # 初始化数据库插件相关属性
        self.database_plugin_activated = False
        self.database_plugin_config = None
        self.database_plugin = None
        # 管理员配置文件路径
        self.admin_config_path = os.path.join(self.PLUGIN_DIR, "admins.json")
        self.admins = self._load_admins()
        # 评级配置文件路径
        self.rating_config_path = os.path.join(self.PLUGIN_DIR, "rating_config.json")
        self.rating_config = self._load_rating_config()
        
    def _load_admins(self):
        """加载管理员配置"""
        if os.path.exists(self.admin_config_path):
            try:
                with open(self.admin_config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("admins", [])
            except Exception as e:
                logger.error(f"加载管理员配置失败: {e}")
                return []
        else:
            # 创建默认配置文件
            default_admins = []
            self._save_admins(default_admins)
            return default_admins
    
    def _save_admins(self, admins):
        """保存管理员配置"""
        try:
            with open(self.admin_config_path, 'w', encoding='utf-8') as f:
                json.dump({"admins": admins}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存管理员配置失败: {e}")
    
    def _load_rating_config(self):
        """加载评级配置"""
        if os.path.exists(self.rating_config_path):
            try:
                with open(self.rating_config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载评级配置失败: {e}")
                return self._get_default_rating_config()
        else:
            # 创建默认配置文件
            default_config = self._get_default_rating_config()
            self._save_rating_config(default_config)
            return default_config
    
    def _save_rating_config(self, config):
        """保存评级配置"""
        try:
            with open(self.rating_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存评级配置失败: {e}")
    
    def _get_default_rating_config(self):
        """获取默认评级配置"""
        return {
            "ratings": [
                {"name": "青茶学徒", "min_varieties": 1, "max_varieties": 3, "description": "刚刚踏入茶道之门，还需努力学习~"},
                {"name": "绿茶行者", "min_varieties": 4, "max_varieties": 6, "description": "对绿茶颇有研究，继续加油！"},
                {"name": "乌龙使者", "min_varieties": 7, "max_varieties": 9, "description": "精通多种乌龙茶，技艺渐进！"},
                {"name": "红茶大师", "min_varieties": 10, "max_varieties": 12, "description": "红茶造诣颇深，令人敬佩！"},
                {"name": "普洱宗师", "min_varieties": 13, "max_varieties": 999, "description": "茶道宗师，收藏丰富，令人仰慕！"}
            ],
            "next_rating_text": "下一等级",
            "max_rating_text": "恭喜您达到最高等级！"
        }
    
    def is_admin(self, user_id):
        """检查用户是否为管理员"""
        return user_id in self.admins

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        """
        插件初始化
        """
        logger.info("------ 小茶馆插件 ------")
        logger.info(f"签到图背景图路径设置为: {self.BACKGROUND_PATH}")
        logger.info(f"签到图用户头像路径设置为: {self.PP_PATH}")
        logger.info(f"签到图输出路径设置为: {self.IMAGE_PATH}")
        logger.info(f"如果有问题，请在 https://github.com/furryHM-mrz/astrbot_plugin_furry_cg/issues 提出 issue")
        logger.info("或加作者QQ: 3322969592 进行反馈。")
        # 获取数据库插件元数据
        database_plugin_meta = self.context.get_registered_star("astrbot_plugin_furry_cgsjk")
        # 数据库插件
        if not database_plugin_meta:
            logger.error("未找到数据库插件，请确保 astrbot_plugin_furry_cgsjk 已正确安装")
            self.database_plugin_config = None  # 为了避免后续使用未初始化的属性
            self.database_plugin_activated = False
        elif not database_plugin_meta.activated:
            logger.error("数据库插件未激活，请在插件管理器中启用 astrbot_plugin_furry_cgsjk")
            self.database_plugin_config = None
            self.database_plugin_activated = False
        else:
            # 获取数据库插件实例
            self.database_plugin = database_plugin_meta.star_cls
            self.database_plugin_config = self.database_plugin.config
            self.database_plugin_activated = True
            try:
                # 使用数据库插件实例调用其公开方法
                if self.database_plugin_activated:
                    self.open_databases = self.database_plugin.get_databases
                    self.DATABASE_FILE = self.database_plugin.get_db_path()
            except Exception as e:
                logger.error(f"无法从数据库插件获取所需模块: {e}")
                self.database_plugin_activated = False
        logger.info("------ 小茶馆插件 ------")

    @filter.command("茶馆帮助")
    async def command_menu(self, event: AstrMessageEvent):
        """
        - 显示小茶馆插件指令菜单
        """
        menu = "🍵 欢迎光临小茶馆！指令菜单如下：\n\n"
        menu += "📝 签到相关：\n"
        menu += "  雪泷签到 - 每日签到获取金币\n"
        menu += "🛍 商店相关：\n"
        menu += "  雪泷商店 - 查看茶叶商品\n"
        menu += "  雪泷购买 <商品ID> <数量> - 购买茶叶\n"
        menu += "💰 个人相关：\n"
        menu += "  雪泷背包 - 查看个人背包\n"
        menu += "  雪泷余额 - 查看个人金币余额\n"
        menu += "  雪泷喝茶 <茶叶名称> - 享用背包中的茶叶\n"
        menu += "  雪泷茶艺展示 - 展示茶艺技能获得奖励\n"
        menu += "  雪泷茶叶评级 - 查看茶叶收藏评级\n"
        menu += "  雪泷任务列表 - 查看茶馆任务\n"
        menu += "  雪泷领取奖励 <任务名称> - 领取任务奖励\n"
        menu += "👑 管理员相关：\n"
        menu += "  雪泷上架 <名称> <库存> <类型> <价格> <描述> - 上架新茶叶\n"
        menu += "  雪泷下架 <商品ID> - 下架茶叶商品\n"
        menu += "  雪泷补货 <商品ID> <数量> - 为茶叶商品补货\n"
        menu += "  雪泷配置评级 - 查看和配置茶叶评级标准\n"
        menu += "📖 其他：\n"
        menu += "  雪泷茶馆帮助 - 显示此帮助菜单\n"
        
        yield event.plain_result(menu)

    def getGroupUserIdentity(self, is_admin: bool, user_id: str, owner: str):
        """
        判断用户在群内的身份。
        """
        if user_id == owner:
            return "群主"
        elif is_admin:
            return "管理员"
        else:
            return "普通用户"

    # -------------------------- 新增茶艺展示功能 --------------------------
    @filter.command("茶艺展示")
    async def tea_art_show(self, event: AstrMessageEvent):
        """
        - 展示茶艺技能，获得金币奖励
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，茶艺展示功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")

            return
            
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                # 检查用户背包中的茶叶种类和数量
                items = db_backpack.query_backpack()
                
                if not items:
                    yield event.plain_result(f"{user_name} 的背包中没有茶叶，无法进行茶艺展示。\n请先购买一些茶叶吧！")
                    return
                
                # 计算茶艺展示奖励
                tea_varieties = len(items)  # 茶叶种类数
                total_teas = sum(item[3] for item in items)  # 茶叶总数量
                
                # 基础奖励 + 种类奖励 + 数量奖励
                base_reward = 20  # 基础奖励20金币
                variety_bonus = tea_varieties * 5  # 每种茶叶额外奖励5金币
                quantity_bonus = min(total_teas, 50)  # 茶叶数量奖励，最多50金币
                
                total_reward = base_reward + variety_bonus + quantity_bonus
                
                # 添加金币奖励
                db_economy.add_economy(total_reward)
                
                # 生成展示结果
                result = f"🍵 {user_name} 的茶艺展示\n\n"
                result += f"展示了 {tea_varieties} 种茶叶，共计 {total_teas} 份\n"
                result += f"基础奖励: {base_reward} 金币\n"
                result += f"种类奖励: {variety_bonus} 金币\n"
                result += f"数量奖励: {quantity_bonus} 金币\n"
                result += f"总计获得: {total_reward} 金币\n\n"
                result += "茶香四溢，技艺精湛！观众们纷纷鼓掌叫好~"
                
                yield event.plain_result(result)
                
        except Exception as e:
            logger.exception(f"茶艺展示失败: {e}")
            yield event.plain_result("茶艺展示失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    # -------------------------- 茶叶评级系统 --------------------------
    @filter.command("茶叶评级")
    async def tea_rating(self, event: AstrMessageEvent):
        """
        - 查看用户的茶叶收藏评级
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，茶叶评级功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                # 获取用户背包中的茶叶
                items = db_backpack.query_backpack()
                
                if not items:
                    yield event.plain_result(f"{user_name} 的背包空空如也，暂无评级。\n快去购买一些茶叶丰富你的收藏吧！")
                    return
                
                # 计算评级参数
                tea_varieties = len(items)  # 茶叶种类数
                total_teas = sum(item[3] for item in items)  # 茶叶总数量
                total_value = sum(item[3] * item[5] for item in items)  # 茶叶总价值
                
                # 评级标准
                # 青茶学徒 (1-3种茶叶)
                # 绿茶行者 (4-6种茶叶)
                # 乌龙使者 (7-9种茶叶)
                # 红茶大师 (10-12种茶叶)
                # 普洱宗师 (13+种茶叶)
                
                if tea_varieties < 4:
                    rating = "青茶学徒"
                    next_rating = "绿茶行者"
                    next_requirement = f"还需收集 {4-tea_varieties} 种茶叶"
                elif tea_varieties < 7:
                    rating = "绿茶行者"
                    next_rating = "乌龙使者"
                    next_requirement = f"还需收集 {7-tea_varieties} 种茶叶"
                elif tea_varieties < 10:
                    rating = "乌龙使者"
                    next_rating = "红茶大师"
                    next_requirement = f"还需收集 {10-tea_varieties} 种茶叶"
                elif tea_varieties < 13:
                    rating = "红茶大师"
                    next_rating = "普洱宗师"
                    next_requirement = f"还需收集 {13-tea_varieties} 种茶叶"
                else:
                    rating = "普洱宗师"
                    next_rating = "已达最高等级"
                    next_requirement = ""
                
                # 生成评级结果
                result = f"📜 {user_name} 的茶叶评级\n\n"
                result += f"评级: {rating}\n"
                result += f"收藏种类: {tea_varieties} 种\n"
                result += f"收藏数量: {total_teas} 份\n"
                result += f"收藏价值: {total_value:.2f} 金币\n"
                
                if next_requirement:
                    result += f"\n下一等级: {next_rating}\n"
                    result += f"升级要求: {next_requirement}\n"
                else:
                    result += f"\n恭喜您达到最高等级！\n"
                
                # 添加评级描述
                rating_descriptions = {
                    "青茶学徒": "刚刚踏入茶道之门，还需努力学习~",
                    "绿茶行者": "对绿茶颇有研究，继续加油！",
                    "乌龙使者": "精通多种乌龙茶，技艺渐进！",
                    "红茶大师": "红茶造诣颇深，令人敬佩！",
                    "普洱宗师": "茶道宗师，收藏丰富，令人仰慕！"
                }
                
                result += f"\n{rating_descriptions[rating]}"
                
                yield event.plain_result(result)
                
        except Exception as e:
            logger.exception(f"茶叶评级查询失败: {e}")
            yield event.plain_result("茶叶评级查询失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    # -------------------------- 任务系统 --------------------------
    # 删除重复的tea_tasks命令实现，使用view_tasks作为唯一入口

    @filter.command("任务列表")
    async def view_tasks(self, event: AstrMessageEvent):
        """
        - 查看茶馆任务
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，任务功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return

        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, db_task, db_backpack, db_store):
                # 初始化默认任务（包括每日随机任务）
                self._init_default_tasks(db_task, user_id)
                
                # 获取用户任务
                tasks = db_task.get_user_tasks()
                
                if not tasks:
                    yield event.plain_result(f"{user_name} 暂无任务。\n每天凌晨会刷新任务列表哦~")
                    return
                
                # 分类任务
                daily_tasks = [task for task in tasks if task[9] == '每日任务']
                weekly_tasks = [task for task in tasks if task[9] == '每周任务']
                special_tasks = [task for task in tasks if task[9] == '特殊任务']
                
                # 生成任务列表
                result = f"📜 {user_name} 的茶馆任务\n\n"
                
                # 显示每日任务
                if daily_tasks:
                    result += "【每日任务】\n"
                    for task in daily_tasks:
                        # id, user_id, task_id, task_name, task_description, task_progress, task_target, reward, status, task_type
                        _, _, task_id, task_name, task_description, task_progress, task_target, reward, status, _ = task
                        status_icon = "✅" if status == '已完成' else "⏳"
                        if status == '已领取':
                            status_icon = "🎁"
                        result += f"{status_icon} {task_name} - {task_description}\n"
                        result += f"   进度: {task_progress}/{task_target} | 奖励: {reward} 金币\n\n"
                
                # 显示每周任务
                if weekly_tasks:
                    result += "【每周任务】\n"
                    for task in weekly_tasks:
                        # id, user_id, task_id, task_name, task_description, task_progress, task_target, reward, status, task_type
                        _, _, task_id, task_name, task_description, task_progress, task_target, reward, status, _ = task
                        status_icon = "✅" if status == '已完成' else "⏳"
                        if status == '已领取':
                            status_icon = "🎁"
                        result += f"{status_icon} {task_name} - {task_description}\n"
                        result += f"   进度: {task_progress}/{task_target} | 奖励: {reward} 金币\n\n"
                
                # 显示特殊任务
                if special_tasks:
                    result += "【特殊任务】\n"
                    for task in special_tasks:
                        # id, user_id, task_id, task_name, task_description, task_progress, task_target, reward, status, task_type
                        _, _, task_id, task_name, task_description, task_progress, task_target, reward, status, _ = task
                        status_icon = "✅" if status == '已完成' else "⏳"
                        if status == '已领取':
                            status_icon = "🎁"
                        result += f"{status_icon} {task_name} - {task_description}\n"
                        result += f"   进度: {task_progress}/{task_target} | 奖励: {reward} 金币\n\n"
                
                result += "完成任务可获得金币奖励！\n\n"
                result += "使用 雪泷领取奖励 <任务名称> 来领取已完成任务的奖励！"
                
                yield event.plain_result(result)
                
        except Exception as e:
            logger.exception(f"任务查询失败: {e}")
            yield event.plain_result("任务查询失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    # -------------------------- 任务功能 --------------------------
    @filter.command("领取奖励")
    async def claim_reward(self, event: AstrMessageEvent, args: tuple):
        """
        - 领取任务奖励 雪泷领取奖励 <任务名称>
        """
        # 添加调试信息
        logger.info(f"收到领取奖励命令: 消息内容='{event.message_obj.message}', 参数='{args}'")
        
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，奖励领取功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return

        # 修复参数解析问题，从原始消息中提取任务名称
        raw_message = event.message_obj.message
        if isinstance(raw_message, list) and len(raw_message) > 0:
            # 如果是消息段列表，提取文本内容
            plain_texts = [seg.text for seg in raw_message if hasattr(seg, 'type') and seg.type == 'Plain']
            full_text = ''.join(plain_texts)
        else:
            full_text = str(raw_message)
        
        # 从完整消息中提取任务名称（去掉命令前缀）
        prefix = "雪泷领取奖励"
        if full_text.startswith(prefix):
            task_input = full_text[len(prefix):].strip()
        else:
            # 如果无法从完整消息中提取，则使用原来的参数拼接方式作为备选
            task_input = ' '.join(args).strip()
            
        logger.info(f"解析后的任务输入: '{task_input}'")
        
        if not task_input:
            yield event.plain_result("参数不足，请使用 雪泷领取奖励 <任务名称>")
            return
        
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, db_task, db_backpack, db_store):
                # 获取所有任务
                tasks = db_task.get_user_tasks()
                
                # 查找匹配的任务
                task = None
                for t in tasks:
                    # id, user_id, task_id, task_name, task_description, task_progress, task_target, reward, status, task_type
                    _, _, task_id, task_name, task_description, task_progress, task_target, reward, status, _ = t
                    
                    # 调试信息
                    logger.info(f"尝试匹配任务: 用户输入='{task_input}', 任务名称='{task_name}', 任务描述='{task_description}'")
                    
                    # 多种匹配方式:
                    # 1. 直接匹配任务名称
                    # 2. 匹配任务描述
                    # 3. 匹配随机任务的简化名称 (去除"今日挑战: "前缀)
                    # 4. 匹配用户可能输入的部分名称
                    if (task_name == task_input or 
                        task_description == task_input or 
                        (task_name.startswith("今日挑战: ") and task_name[7:] == task_input) or
                        (task_name.startswith("今日挑战: ") and task_name.endswith(task_input))):
                        task = t
                        logger.info(f"成功匹配任务: {task_name}")
                        break
                
                if not task:
                    # 如果还没找到，提供更详细的错误信息
                    task_list = "\n".join([f"  - {t[3]} ({t[4]})" if not t[3].startswith("今日挑战: ") else f"  - {t[3]}" for t in tasks])
                    logger.info(f"未找到任务: 用户输入='{task_input}', 可用任务列表={task_list}")
                    yield event.plain_result(f"未找到该任务，请检查任务名称是否正确。\n可用的任务列表:\n{task_list}")
                    return
                
                # id, user_id, task_id, task_name, task_description, task_progress, task_target, reward, status, task_type
                _, _, task_id, task_display_name, task_description, task_progress, task_target, reward, status, _ = task
                
                # 检查任务是否已完成
                if status != '已完成':
                    yield event.plain_result(f"任务 '{task_display_name}' 尚未完成，无法领取奖励。\n当前进度: {task_progress}/{task_target}")
                    return
                
                # 检查任务奖励是否已经领取过
                if status == '已领取':
                    yield event.plain_result("你已经领取过了")
                    return
                
                # 发放奖励
                db_economy.add_economy(reward)
                
                # 更新任务状态为已领取
                claimed = db_task.claim_reward(task_id)
                if not claimed:
                    yield event.plain_result("你已经领取过了")
                    return
                
                yield event.plain_result(f"🎉 恭喜 {user_name}！\n任务 '{task_display_name}' 的奖励已发放。\n获得 {reward} 金币。")
                
        except Exception as e:
            logger.exception(f"领取奖励失败: {e}")
            yield event.plain_result("领取奖励失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    def _init_default_tasks(self, db_task, user_id):
        """
        初始化默认任务
        """
        from datetime import datetime, timedelta
        import random
        
        # 检查是否已有任务，避免重复创建基本任务
        existing_tasks = db_task.get_user_tasks()
        has_daily_tasks = any(task[9] == '每日任务' and not task[2].startswith('daily_random_') for task in existing_tasks)
        
        # 基础任务
        default_tasks = [
            ('daily_drink_tea', '品茶师', '品尝3种不同的茶叶', 3, 50, '每日任务'),
            ('daily_buy_tea', '采购员', '购买茶叶2次', 2, 30, '每日任务'),
            ('weekly_collect_tea', '收藏家', '收集5种不同的茶叶', 5, 100, '每周任务')
        ]
        
        # 只有当没有每日任务时才创建基础任务
        if not has_daily_tasks:
            for task_id, task_name, task_desc, target, reward, task_type in default_tasks:
                db_task.create_task(task_id, task_name, task_desc, target, reward, task_type)
        
        # 更新每日随机任务（确保每天都有新的随机任务）
        db_task.update_daily_random_task()

    def _update_task_progress(self, db_task, task_id, increment, unique_check=None):
        """
        更新任务进度
        :param db_task: TaskDB实例
        :param task_id: 任务ID
        :param increment: 进度增量
        :param unique_check: 唯一性检查参数（用于检查是否为不同种类的茶叶）
        """
        try:
            # 获取任务信息
            task = db_task.get_task_by_id(task_id)
            if not task or task[8] == '已完成':  # status字段
                # 检查是否是每日随机任务
                from datetime import datetime
                today = datetime.now().date()
                daily_random_task_id = f"daily_random_{today.strftime('%Y%m%d')}"
                
                # 如果是今天的随机任务，也尝试获取
                if task_id == daily_random_task_id:
                    task = db_task.get_task_by_id(task_id)
                    if not task or task[8] == '已完成':
                        return
                else:
                    return
            
            current_progress = task[5]  # task_progress字段
            target = task[6]  # task_target字段
            
            # 对于唯一性检查任务（如品尝不同茶叶）
            if unique_check and task_id == "daily_drink_tea":
                # 这里可以扩展实现记录已品尝的茶叶种类，避免重复计算
                # 简化处理：每次调用都增加进度
                pass
            
            # 更新进度
            new_progress = min(current_progress + increment, target)
            db_task.update_task_progress(task_id, new_progress)
            
            # 检查任务是否完成
            if new_progress >= target:
                db_task.complete_task(task_id)
                
        except Exception as e:
            logger.warning(f"更新任务进度失败: {e}")

            db_task.update_task_progress(task_id, new_progress)
            
            # 检查任务是否完成
            if new_progress >= target:
                db_task.complete_task(task_id)
                
        except Exception as e:
            logger.warning(f"更新任务进度失败: {e}")

    # -------------------------- 商店功能 --------------------------
    @filter.command("商店")
    async def shop(self, event: AstrMessageEvent):
        """
        - 查看商店中的所有茶叶商品
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，商店功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                # 使用新的连续ID方法
                teas = db_store.get_all_tea_store_with_continuous_id()
                if not teas:
                    yield event.plain_result("商店暂无商品。")
                    return
                    
                # 构建商店信息
                shop_info = "----- 茶馆商店 -----\n"
                shop_info += "输入 雪泷购买 <商品ID> <数量> 来购买茶叶\n\n"
                
                # 创建ID映射，使用连续序号
                id_mapping = {}  # 显示ID -> 实际数据库ID
                display_id = 1
                
                for tea in teas:
                    # id, tea_name, quantity, tea_type, price, description
                    tea_id, tea_name, quantity, tea_type, price, description = tea
                    # 获取实际ID用于映射
                    actual_tea_id = db_store.get_actual_id_by_continuous_id(tea_id)
                    id_mapping[tea_id] = actual_tea_id
                    
                    shop_info += f"ID: {tea_id}\n"
                    shop_info += f"茶叶名称: {tea_name}\n"
                    shop_info += f"类型: {tea_type}\n"
                    shop_info += f"价格: {price} 金币\n"
                    shop_info += f"库存: {quantity}\n"
                    shop_info += f"描述: {description}\n"
                    shop_info += "----------\n"
                    
                    display_id += 1
                
                # 保存ID映射到用户会话中
                self._id_mapping = id_mapping
                
                yield event.plain_result(shop_info)
        except Exception as e:
            logger.exception(f"查看商店失败: {e}")
            yield event.plain_result("查看商店失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    @filter.command("背包")
    async def view_backpack(self, event: AstrMessageEvent):
        """
        - 查看个人背包
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，背包功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                items = db_backpack.query_backpack()
                
                if not items:
                    yield event.plain_result(f"{user_name} 的背包空空如也。")
                    return
                
                # 构建背包信息
                backpack_info = f"----- {user_name} 的背包 -----\n\n"
                total_items = 0
                for item in items:
                    # id, user_id, item_name, item_count, item_type, item_value
                    item_id, _, item_name, item_count, item_type, item_value = item
                    backpack_info += f"物品名称: {item_name}\n"
                    backpack_info += f"数量: {item_count}\n"
                    backpack_info += f"类型: {item_type}\n"
                    backpack_info += f"单价: {item_value} 金币\n"
                    backpack_info += f"总价值: {item_value * item_count:.2f} 金币\n"
                    backpack_info += "----------\n"
                    total_items += item_count
                    
                backpack_info += f"\n总计物品数量: {total_items}"
                
                yield event.plain_result(backpack_info)
        except Exception as e:
            logger.exception(f"查看背包失败: {e}")
            yield event.plain_result("查看背包失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    @filter.command("余额")
    async def view_balance(self, event: AstrMessageEvent):
        """
        - 查看个人余额
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，余额查询功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                balance = db_economy.get_economy()
                yield event.plain_result(f"{user_name} 的余额: {balance:.2f} 金币")
        except Exception as e:
            logger.exception(f"查询余额失败: {e}")
            yield event.plain_result("查询余额失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    @filter.command("喝茶")
    async def drink_tea(self, event: AstrMessageEvent, args: tuple):
        """
        - 从背包中选择茶叶享用 雪泷喝茶 <茶叶名称>
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，喝茶功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        # 添加调试信息
        logger.info(f"喝茶命令接收到参数: {args}, 参数数量: {len(args)}")
        
        # 检查参数是否为空
        if not args or len(args) < 1:
            yield event.plain_result("参数不足，请使用 雪泷喝茶 <茶叶名称>")
            return
            
        # 修复参数解析问题，从原始消息中提取茶叶名称
        raw_message = event.message_obj.message
        if isinstance(raw_message, list) and len(raw_message) > 0:
            # 如果是消息段列表，提取文本内容
            plain_texts = [seg.text for seg in raw_message if hasattr(seg, 'type') and seg.type == 'Plain']
            full_text = ''.join(plain_texts)
        else:
            full_text = str(raw_message)
        
        # 从完整消息中提取茶叶名称（去掉命令前缀）
        prefix = "雪泷喝茶"
        if full_text.startswith(prefix):
            tea_name = full_text[len(prefix):].strip()
        elif full_text.startswith("喝茶"):
            tea_name = full_text[2:].strip()
        else:
            # 如果无法从完整消息中提取，则使用原来的参数拼接方式作为备选
            tea_name = ' '.join(args).strip()
            
        logger.info(f"解析后的茶叶名称: '{tea_name}'")
        
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, db_task, db_backpack, db_store):
                # 检查背包中是否有这种茶叶
                items = db_backpack.query_backpack()
                target_tea = None
                for item in items:
                    # id, user_id, item_name, item_count, item_type, item_value
                    _, _, item_name, item_count, item_type, _ = item
                    if item_name == tea_name and item_count > 0:
                        target_tea = item
                        break
                
                if not target_tea:
                    yield event.plain_result(f"您的背包中没有 {tea_name} 或数量不足。")
                    return
                
                # 享用茶叶，从背包中移除1个
                removed = db_backpack.remove_item(tea_name, 1)
                if not removed:
                    yield event.plain_result(f"饮用 {tea_name} 失败。")
                    return
                
                # 根据茶叶类型给出不同的回复
                _, _, _, _, tea_type, _ = target_tea
                tea_responses = {
                    '绿茶': f"清淡的绿茶散发着清香，{user_name} 感到一阵清新舒适。",
                    '乌龙茶': f"醇厚的乌龙茶在口中回甘，{user_name} 感到心旷神怡。",
                    '黑茶': f"陈香浓郁的黑茶暖胃舒心，{user_name} 感到浑身温暖。",
                    '红茶': f"香甜的红茶让{user_name}感到温暖和放松。",
                    '白茶': f"清淡的白茶带着自然的香气，{user_name} 感到宁静祥和。",
                    '普通': f"{user_name} 品尝了 {tea_name}，感到十分满足。"
                }
                
                response = tea_responses.get(tea_type, tea_responses['普通'])
                
                # 更新任务进度
                self._update_task_progress(db_task, "daily_drink_tea", 1, unique_check=tea_name)
                
                yield event.plain_result(f"{response}\n您享用了 1 份 {tea_name}，背包中还剩 {target_tea[3]-1} 份。")
        except Exception as e:
            logger.exception(f"喝茶失败: {e}")
            yield event.plain_result("喝茶失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    @filter.command("购买")
    async def buy_tea(self, event: AstrMessageEvent, args: tuple):
        """
        - 购买茶叶 雪泷购买 <商品ID> <数量>
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，购买功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        # 添加调试信息
        logger.info(f"购买命令接收到参数: {args}, 参数数量: {len(args)}")
        
        # 检查参数是否为空或数量不足
        if not args or len(args) < 1:
            # 先显示商店信息，帮助用户了解有哪些商品可以购买
            try:
                user_id = event.get_sender_id()
                with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, db_task, db_backpack, db_store):
                    teas = db_store.get_all_tea_store()
                    if teas:
                        shop_info = "----- 可购买的茶叶商品 -----\n"
                        shop_info += "使用方法: 雪泷购买 <商品ID> <数量>\n"
                        shop_info += "例如: 雪泷购买 1 2 (购买ID为1的商品2份)\n\n"
                        for tea in teas:
                            tea_id, tea_name, quantity, tea_type, price, description = tea
                            shop_info += f"ID: {tea_id} | {tea_name} | 价格: {price}金币 | 库存: {quantity}\n"
                        shop_info += "\n请使用 雪泷购买 <商品ID> <数量> 来购买您喜欢的茶叶"
                        yield event.plain_result(shop_info)
                    else:
                        yield event.plain_result("商店暂无商品，无法购买。")
            except Exception as e:
                logger.exception(f"获取商店信息失败: {e}")
                yield event.plain_result("获取商店信息失败，请稍后再试。")
            return
            
        # 修复参数解析问题，从原始消息中提取参数
        raw_message = event.message_obj.message
        if isinstance(raw_message, list) and len(raw_message) > 0:
            # 如果是消息段列表，提取文本内容
            plain_texts = [seg.text for seg in raw_message if hasattr(seg, 'type') and seg.type == 'Plain']
            full_text = ''.join(plain_texts)
        else:
            full_text = str(raw_message)
        
        # 从完整消息中提取参数（去掉命令前缀）
        prefix = "雪泷购买"
        if full_text.startswith(prefix):
            params = full_text[len(prefix):].strip().split()
        elif full_text.startswith("购买"):
            params = full_text[2:].strip().split()
        else:
            # 如果无法从完整消息中提取，则使用原来的参数作为备选
            params = list(args)
            
        logger.info(f"解析后的参数: {params}")
        
        # 检查参数是否为空或数量不足
        if not args or len(args) < 1:
            # 先显示商店信息，帮助用户了解有哪些商品可以购买
            try:
                user_id = event.get_sender_id()
                with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, db_task, db_backpack, db_store):
                    teas = db_store.get_all_tea_store()
                    if teas:
                        shop_info = "----- 可购买的茶叶商品 -----\n"
                        shop_info += "使用方法: 雪泷购买 <商品ID> <数量>\n"
                        shop_info += "例如: 雪泷购买 1 2 (购买ID为1的商品2份)\n\n"
                        
                        # 创建ID映射，使用连续序号
                        id_mapping = {}
                        display_id = 1
                        
                        for tea in teas:
                            tea_id, tea_name, quantity, tea_type, price, description = tea
                            id_mapping[display_id] = tea_id
                            shop_info += f"ID: {display_id} | {tea_name} | 价格: {price}金币 | 库存: {quantity}\n"
                            display_id += 1
                            
                        shop_info += "\n请使用 雪泷购买 <商品ID> <数量> 来购买您喜欢的茶叶"
                        yield event.plain_result(shop_info)
                    else:
                        yield event.plain_result("商店暂无商品，无法购买。")
            except Exception as e:
                logger.exception(f"获取商店信息失败: {e}")
                yield event.plain_result("获取商店信息失败，请稍后再试。")
            return
            
        # 检查参数数量
        if len(params) < 2:
            yield event.plain_result("参数不足，请使用 雪泷购买 <商品ID> <数量>")
            return
            
        tea_id_str, quantity_str = params[0], params[1]
        
        try:
            tea_id = int(tea_id_str)
            quantity = int(quantity_str)
        except ValueError:
            yield event.plain_result("参数错误，商品ID和数量必须是数字")
            return
            
        if quantity <= 0:
            yield event.plain_result("购买数量必须大于0")
            return
            
        user_id = event.get_sender_id()
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, db_task, db_backpack, db_store):
                # 检查ID映射
                actual_tea_id = tea_id
                if hasattr(self, '_id_mapping') and tea_id in self._id_mapping:
                    actual_tea_id = self._id_mapping[tea_id]
                
                # 使用新的方法通过连续ID获取实际ID
                actual_tea_id = db_store.get_actual_id_by_continuous_id(tea_id)
                    
                tea_id, tea_name, stock_quantity, tea_type, price, description = tea_item
                
                # 检查库存
                if stock_quantity < quantity:
                    yield event.plain_result(f"库存不足，当前库存仅有 {stock_quantity} 份")
                    return
                    
                # 计算总价
                total_price = price * quantity
                
                # 检查用户余额
                user_balance = db_economy.get_economy()
                if user_balance < total_price:
                    yield event.plain_result(f"余额不足，需要 {total_price} 金币，您当前有 {user_balance} 金币")
                    return
                    
                # 扣除金币
                db_economy.reduce_economy(total_price)
                
                # 添加到背包
                db_backpack.add_item(tea_name, quantity, tea_type, price)
                
                # 更新库存
                db_store.update_tea_quantity(actual_tea_id, -quantity)
                
                # 更新任务进度（如果有的话）
                self._update_task_progress(db_task, "daily_buy_tea", 1)
                
                yield event.plain_result(f"购买成功！\n购买了 {quantity} 份 {tea_name}\n花费 {total_price} 金币\n茶叶已放入您的背包")
                
        except Exception as e:
            logger.exception(f"购买失败: {e}")
            yield event.plain_result("购买失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    # -------------------------- 管理员功能 --------------------------
    @filter.command("上架")
    async def add_tea(self, event: AstrMessageEvent, args: tuple):
        """
        - 管理员上架新茶叶 雪泷上架 <茶叶名称> <库存> <类型> <价格> <描述>
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，上架功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        
        # 检查是否为管理员（使用配置文件方式）
        if not self.is_admin(user_id):
            yield event.plain_result("权限不足，只有管理员才能上架商品")
            return
        
        # 添加调试信息
        logger.info(f"上架命令接收到参数: {args}, 参数数量: {len(args)}")
        logger.info(f"完整消息内容: {event.message_obj.message}")
            
        # 初始化参数
        tea_name = ""
        quantity_str = ""
        tea_type = ""
        price_str = ""
        description = ""
        
        # 检查参数是否足够
        if len(args) < 1:
            yield event.plain_result("参数不足，请使用 雪泷上架 <茶叶名称> <库存> <类型> <价格> <描述>")
            return
            
        # 如果参数不足5个，尝试从完整消息中解析
        if len(args) < 5:
            # 从完整消息中解析参数
            message_obj = event.message_obj.message
            
            # 处理消息对象可能是列表的情况
            if isinstance(message_obj, list):
                # 提取消息文本内容
                message_text = ""
                for item in message_obj:
                    if hasattr(item, 'text'):
                        message_text += item.text
                    else:
                        message_text += str(item)
            else:
                message_text = str(message_obj)
            
            # 移除命令前缀
            message = message_text
            if message.startswith("雪泷上架"):
                message = message[4:].strip()
            elif message.startswith("上架"):
                message = message[2:].strip()
            
            # 使用更智能的方式解析参数
            # 将消息按空格分割，然后重新组合以适应5个参数的要求
            parts = message.split()
            if len(parts) >= 5:
                # 茶叶名称可能是多个单词，需要特殊处理
                # 假设格式为: 茶叶名称 数量 类型 价格 描述...
                tea_name = parts[0]
                quantity_str = parts[1]
                tea_type = parts[2]
                price_str = parts[3]
                description = ' '.join(parts[4:])  # 描述可能包含多个单词
                
                # 如果茶叶名称明显不完整（以常见的结尾词结尾），尝试合并更多部分
                # 检查是否有更合理的茶叶名称组合
                potential_name_parts = [parts[0]]
                i = 1
                # 常见的茶叶名称可能的结尾词
                name_endings = ['茶', '清茶', '绿茶', '红茶', '乌龙茶', '白茶', '黑茶', '花茶', '奶茶']
                while i < len(parts) - 3:  # 确保后面还有至少3个参数（数量、类型、价格）
                    potential_name_parts.append(parts[i])
                    potential_name = ' '.join(potential_name_parts)
                    # 如果当前组合以常见的茶叶名称结尾，可能是完整的茶叶名称
                    if any(potential_name.endswith(ending) for ending in name_endings):
                        tea_name = potential_name
                        # 更新其他参数的索引
                        remaining_parts = parts[i+1:]
                        if len(remaining_parts) >= 4:
                            quantity_str = remaining_parts[0]
                            tea_type = remaining_parts[1]
                            price_str = remaining_parts[2]
                            description = ' '.join(remaining_parts[3:])
                        break
                    i += 1
            else:
                yield event.plain_result("参数不足，请使用 雪泷上架 <茶叶名称> <库存> <类型> <价格> <描述>")
                return
        else:
            # 直接从args中提取参数，但要考虑茶叶名称可能包含空格的情况
            if len(args) >= 5:
                tea_name = args[0]
                quantity_str = args[1]
                tea_type = args[2]
                price_str = args[3]
                description = ' '.join(args[4:])  # 描述可能包含多个单词
            else:
                yield event.plain_result("参数不足，请使用 雪泷上架 <茶叶名称> <库存> <类型> <价格> <描述>")
                return
        
        # 处理用户可能在参数中添加的标签
        if tea_name.startswith("茶叶名称"):
            tea_name = tea_name[4:]  # 去掉"茶叶名称"前缀
        
        if tea_type.startswith("类型"):
            tea_type = tea_type[2:]  # 去掉"类型"前缀
        
        if quantity_str.startswith("库存"):
            quantity_str = quantity_str[2:]  # 去掉"库存"前缀
        
        if price_str.startswith("价格"):
            price_str = price_str[2:]  # 去掉"价格"前缀
        
        if description.startswith("描述"):
            description = description[2:]  # 去掉"描述"前缀
        
        # 尝试转换数量和价格
        try:
            quantity = int(quantity_str)
            price = float(price_str)
        except ValueError:
            yield event.plain_result("参数错误，库存必须是整数，价格必须是数字")
            return
        
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                # 添加到商店
                tea_id = db_store.add_tea_to_store(tea_name, quantity, tea_type, price, description)
                
                yield event.plain_result(f"上架成功！\n茶叶名称: {tea_name}\n库存: {quantity}\n类型: {tea_type}\n价格: {price} 金币\n描述: {description}\n商品ID: {tea_id}")
                
        except Exception as e:
            logger.exception(f"上架失败: {e}")
            yield event.plain_result("上架失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()

    @filter.command("下架")
    async def remove_tea(self, event: AstrMessageEvent, args: tuple):
        """
        - 管理员下架茶叶 雪泷下架 <商品ID>
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，下架功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        
        # 检查是否为管理员（使用配置文件方式）
        if not self.is_admin(user_id):
            yield event.plain_result("权限不足，只有管理员才能下架商品")
            return

        # 添加调试信息
        logger.info(f"下架命令接收到参数: {args}, 参数数量: {len(args)}")
        
        # 检查参数是否为空或数量不足
        if not args or len(args) < 1:
            yield event.plain_result("参数不足，请使用 雪泷下架 <商品ID>")
            return
            
        # 修复参数解析问题，从原始消息中提取参数
        raw_message = event.message_obj.message
        if isinstance(raw_message, list) and len(raw_message) > 0:
            # 如果是消息段列表，提取文本内容
            plain_texts = [seg.text for seg in raw_message if hasattr(seg, 'type') and seg.type == 'Plain']
            full_text = ''.join(plain_texts)
        else:
            full_text = str(raw_message)
        
        # 从完整消息中提取参数（去掉命令前缀）
        prefix = "雪泷下架"
        if full_text.startswith(prefix):
            params = full_text[len(prefix):].strip().split()
        elif full_text.startswith("下架"):
            params = full_text[2:].strip().split()
        else:
            # 如果无法从完整消息中提取，则使用原来的参数作为备选
            params = list(args)
            
        logger.info(f"解析后的参数: {params}")
        
        # 检查参数数量
        if len(params) < 1:
            yield event.plain_result("参数不足，请使用 雪泷下架 <商品ID>")
            return
            
        tea_id_str = params[0]
        
        try:
            tea_id = int(tea_id_str)
        except ValueError:
            yield event.plain_result("参数错误，商品ID必须是数字")
            return

        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                # 使用新的方法通过连续ID获取实际ID
                actual_tea_id = db_store.get_actual_id_by_continuous_id(tea_id)
                
                if not actual_tea_id:
                    # 如果商品不存在，显示商店信息帮助用户选择正确的商品
                    try:
                        # 使用新的连续ID方法
                        teas = db_store.get_all_tea_store_with_continuous_id()
                        if teas:
                            tea_list = "当前商店中的商品列表：\n"
                            # 创建ID映射，使用连续序号
                            id_mapping = {}
                            
                            for tea in teas:
                                tea_id, tea_name, quantity, tea_type, price, description = tea
                                # 获取实际ID用于映射
                                actual_tea_id = db_store.get_actual_id_by_continuous_id(tea_id)
                                id_mapping[tea_id] = actual_tea_id
                                tea_list += f"ID: {tea_id} | {tea_name} | 库存: {quantity}\n"
                                
                            # 保存ID映射到用户会话中
                            self._id_mapping = id_mapping
                                
                            yield event.plain_result(f"未找到该商品，请检查商品ID是否正确\n{tea_list}")
                        else:
                            yield event.plain_result("未找到该商品，且商店中暂无其他商品")
                    except Exception as e:
                        logger.exception(f"获取商店信息失败: {e}")
                        yield event.plain_result("未找到该商品，请检查商品ID是否正确。")
                    return
                
                # 获取商品信息
                tea_item = db_store.get_tea_store_item(actual_tea_id)
                # 执行下架操作
                db_store.remove_tea_from_store(actual_tea_id)
                
                yield event.plain_result(f"下架成功！\n"
                                       f"商品: {tea_item[1]}")
                
        except Exception as e:
            logger.exception(f"下架失败: {e}")
            yield event.plain_result("下架失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()


    @filter.command("补货")
    async def restock_tea(self, event: AstrMessageEvent, args: tuple):
        """
        - 管理员为商店中的茶叶补货 雪泷补货 <商品ID> <补货数量>
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，补货功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return
            
        user_id = event.get_sender_id()
        
        # 检查是否为管理员
        if not self.is_admin(user_id):
            yield event.plain_result("权限不足，只有管理员才能为商品补货")
            return

        # 添加调试信息
        logger.info(f"补货命令接收到参数: {args}, 参数数量: {len(args)}")
        
        # 检查参数是否为空或数量不足
        if not args or len(args) < 1:
            yield event.plain_result("参数不足，请使用 雪泷补货 <商品ID> <补货数量>")
            return
            
        # 修复参数解析问题，从原始消息中提取参数
        raw_message = event.message_obj.message
        if isinstance(raw_message, list) and len(raw_message) > 0:
            # 如果是消息段列表，提取文本内容
            plain_texts = [seg.text for seg in raw_message if hasattr(seg, 'type') and seg.type == 'Plain']
            full_text = ''.join(plain_texts)
        else:
            full_text = str(raw_message)
        
        # 从完整消息中提取参数（去掉命令前缀）
        prefix = "雪泷补货"
        if full_text.startswith(prefix):
            params = full_text[len(prefix):].strip().split()
        elif full_text.startswith("补货"):
            params = full_text[2:].strip().split()
        else:
            # 如果无法从完整消息中提取，则使用原来的参数作为备选
            params = list(args)
            
        logger.info(f"解析后的参数: {params}")
        
        # 检查参数数量
        if len(params) < 2:
            yield event.plain_result("参数不足，请使用 雪泷补货 <商品ID> <补货数量>")
            return
            
        tea_id_str, quantity_str = params[0], params[1]
        
        try:
            tea_id = int(tea_id_str)
            quantity = int(quantity_str)
        except ValueError:
            yield event.plain_result("参数错误，商品ID和补货数量必须是数字")
            return
            
        if quantity <= 0:
            yield event.plain_result("补货数量必须大于0")
            return

        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                # 检查ID映射
                actual_tea_id = tea_id
                if hasattr(self, '_id_mapping') and tea_id in self._id_mapping:
                    actual_tea_id = self._id_mapping[tea_id]
                
                # 使用新的方法通过连续ID获取实际ID
                actual_tea_id = db_store.get_actual_id_by_continuous_id(tea_id)
                
                if not actual_tea_id:
                    # 如果商品不存在，显示商店信息帮助用户选择正确的商品
                    try:
                        # 使用新的连续ID方法
                        teas = db_store.get_all_tea_store_with_continuous_id()
                        if teas:
                            tea_list = "当前商店中的商品列表：\n"
                            # 创建ID映射，使用连续序号
                            id_mapping = {}
                            
                            for tea in teas:
                                tea_id, tea_name, quantity, tea_type, price, description = tea
                                # 获取实际ID用于映射
                                actual_tea_id = db_store.get_actual_id_by_continuous_id(tea_id)
                                id_mapping[tea_id] = actual_tea_id
                                tea_list += f"ID: {tea_id} | {tea_name} | 库存: {quantity}\n"
                                
                            # 保存ID映射到用户会话中
                            self._id_mapping = id_mapping
                                
                            yield event.plain_result(f"未找到该商品，请检查商品ID是否正确\n{tea_list}")
                        else:
                            yield event.plain_result("未找到该商品，且商店中暂无其他商品")
                    except Exception as e:
                        logger.exception(f"获取商店信息失败: {e}")
                        yield event.plain_result("未找到该商品，请检查商品ID是否正确。")
                    return
                
                # 执行补货操作
                updated_tea = db_store.restock_tea(actual_tea_id, quantity)
                
                yield event.plain_result(f"补货成功！\n"
                                       f"商品: {updated_tea[1]}\n"
                                       f"补货数量: {quantity}\n"
                                       f"补货后库存: {updated_tea[2]}")
                
        except Exception as e:
            logger.exception(f"补货失败: {e}")
            yield event.plain_result("补货失败，请稍后再试。")
        finally:
            # 确保数据库连接关闭
            if self.database_plugin_activated and hasattr(self.database_plugin, 'close_databases'):
                self.database_plugin.close_databases()


    @filter.command("签到")
    async def sign_in(self, event: AstrMessageEvent):
        """
        - 签到 [生成签到卡片并发送]
        """
        if not self.database_plugin_activated:
            yield event.plain_result("数据库插件未加载，签到功能无法使用。\n请先安装并启用 astrbot_plugin_furry_cgsjk。\n插件仓库地址：https://github.com/furryHM-mrz/astrbot_plugin_furry_cgsjk")
            return

        user_id = event.get_sender_id()
        try:
            with self.open_databases(self.database_plugin_config, self.DATABASE_FILE, user_id) as (db_user, db_economy, _, db_backpack, db_store):
                user_name = event.get_sender_name()
                group = await event.get_group(group_id=event.message_obj.group_id)
                owner = group.group_owner
                is_admin = event.is_admin()
                identity = self.getGroupUserIdentity(is_admin, user_id, owner)
                formatted_time = get_formatted_time()
                sign_in_count = db_user.query_sign_in_count()[0]  # 获取签到次数的第一个元素
                one_sentence_data = get_one_sentence()

                # 默认值，防止one_sentence获取失败造成错误
                one_sentence = "今日一言获取失败"
                one_sentence_source = "未知"

                if one_sentence_data:
                    one_sentence = one_sentence_data.get("tangdouz", "今日一言获取失败")
                    one_sentence_source = f"————{one_sentence_data.get('from', '未知')} - {one_sentence_data.get('from_who', '未知')}"

                last_sign_in_date = db_user.query_last_sign_in_date()
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                user_economy = db_economy.get_economy()

                sign_in_reward = 0  # 签到奖励
                is_signed_today = (last_sign_in_date == today)

                if not is_signed_today:
                    sign_in_reward = round(random.uniform(50, 100), 2)
                    db_user.update_sign_in(sign_in_reward)
                    db_economy.add_economy(sign_in_reward)
                    user_economy += sign_in_reward

                user_info = [user_id, identity, user_name]
                bottom_left_info = [
                    f"当前时间: {formatted_time}",
                    f"签到日期: {today if not is_signed_today else last_sign_in_date}",
                    f"金币: {user_economy:.2f}"  # 格式化为两位小数
                ]

                bottom_right_top_info = [
                    "今日已签到" if is_signed_today else "签到成功",
                    f"签到天数: {sign_in_count}" if is_signed_today else f"签到天数: {sign_in_count + 1}",
                    f"获取金币: {db_user.query_sign_in_coins() if is_signed_today else sign_in_reward:.2f}"  # 格式化为两位小数
                ]

                bottom_right_bottom_info = [
                    one_sentence,
                    one_sentence_source,
                ]

                # 头像路径
                pp = os.path.join(self.PP_PATH, f"{user_id}.png")
                if os.path.exists(pp):
                    avatar_path = pp
                else:
                    di = download_image(user_id, self.PP_PATH)
                    if di:
                        avatar_path = pp
                    else:
                        avatar_path = os.path.join(self.PLUGIN_DIR, "avatar.png")
                # 背景图路径
                files = os.listdir(self.BACKGROUND_PATH)
                if len(files) == 0:
                    image_folder = self.IMAGE_FOLDER
                else:
                    image_folder = self.BACKGROUND_PATH

                sign_image = create_check_in_card(
                    avatar_path=avatar_path,
                    user_info=user_info,
                    bottom_left_info=bottom_left_info,
                    bottom_right_top_info=bottom_right_top_info,
                    bottom_right_bottom_info=bottom_right_bottom_info,
                    output_path=os.path.join(self.IMAGE_PATH, f"{user_id}.png"),
                    image_folder=image_folder,
                    font_path=self.FONT_PATH
                )
                yield event.image_result(sign_image)

        except Exception as e:
            logger.exception(f"签到失败: {e}")
            yield event.plain_result("签到失败，请稍后再试。")