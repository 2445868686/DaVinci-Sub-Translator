# ================= 用户配置 =================
SCRIPT_NAME    = "DaVinci AI Translator "
SCRIPT_VERSION = "v0.1"
SCRIPT_AUTHOR  = "HEIBA"

SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
WINDOW_WIDTH, WINDOW_HEIGHT = 400, 350
X_CENTER = (SCREEN_WIDTH  - WINDOW_WIDTH ) // 2
Y_CENTER = (SCREEN_HEIGHT - WINDOW_HEIGHT) // 2

SCRIPT_KOFI_URL      = "https://ko-fi.com/heiba"
SCRIPT_WX_URL        = "https://mp.weixin.qq.com/s?__biz=MzUzMTk2MDU5Nw==&mid=2247484626&idx=1&sn=e5eef7e48fbfbf37f208ed9a26c5475a"
SCRIPT_BILIBILI_URL  = "https://space.bilibili.com/385619394"
TTS_KOFI_URL         = "https://ko-fi.com/s/9e769243b5"
TTS_TAOBAO_URL       = "https://item.taobao.com/item.htm?id=808582811947"

CONCURRENCY = 10
MAX_RETRY   = 3
TIMEOUT     = 30

OPENAI_DEFAULT_KEY   = ""
OPENAI_DEFAULT_URL   = "https://api.openai.com"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"

CONTEXT_WINDOW = 1
SYSTEM_PROMPT = """
You are a translation engine.<br/><br/>
Translate the user message into {target_lang}.<br/><br/>
Return ONLY the translated sentence, keep the same meaning.<br/><br/>
Note: For any content that should not be translated
(e.g., proper nouns, code snippets, or other non-translatable elements), "
    "preserve it in its original form.
"""

GOOGLE_PROVIDER = "Google"
AZURE_PROVIDER  = "Microsoft (API Key)"
AI_PROVIDER     = "AI Translator (API Key)"

AZURE_DEFAULT_KEY    = ""
AZURE_DEFAULT_REGION = ""
AZURE_DEFAULT_URL    = "https://api.cognitive.microsofttranslator.com"

# --------------------------------------------
# 语言映射
# --------------------------------------------
AZURE_LANG_CODE_MAP = {  # Microsoft
    "中文（普通话）": "zh-Hans",  "中文（粤语）": "yue",
    "English": "en", "Japanese": "ja", "Korean": "ko", "Spanish": "es",
    "Portuguese": "pt", "French": "fr", "Indonesian": "id", "German": "de",
    "Russian": "ru", "Italian": "it", "Arabic": "ar", "Turkish": "tr",
    "Ukrainian": "uk", "Vietnamese": "vi", "Dutch": "nl",
}
GOOGLE_LANG_CODE_MAP = {   # Google
    "中文（普通话）": "zh-CN", "中文（粤语）": "zh-TW",
    "English": "en", "Japanese": "ja", "Korean": "ko", "Spanish": "es",
    "Portuguese": "pt", "French": "fr", "Indonesian": "id", "German": "de",
    "Russian": "ru", "Italian": "it", "Arabic": "ar", "Turkish": "tr",
    "Ukrainian": "uk", "Vietnamese": "vi", "Dutch": "nl",
}
# ===========================================
import sys
import os, re, json, time, platform,concurrent.futures
from abc import ABC, abstractmethod
import webbrowser
import random
import string

try:
    import requests
    from deep_translator import GoogleTranslator
except ImportError:
    # 1. 获取脚本所在目录（备用）
    script_path = os.path.dirname(os.path.abspath(sys.argv[0]))

    # 2. 根据不同平台设置 Lib 目录为绝对路径
    system = platform.system()
    if system == "Windows":
        # Windows 下 C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\TTS\Lib
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        lib_dir = os.path.join(
            program_data,
            "Blackmagic Design",
            "DaVinci Resolve",
            "Fusion",
            "HB",
            "Translator",
            "Lib"
        )
    elif system == "Darwin":
        # macOS 下 /Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/TTS/Lib
        lib_dir = os.path.join(
            "/Library",
            "Application Support",
            "Blackmagic Design",
            "DaVinci Resolve",
            "Fusion",
            "HB",
            "Translator",
            "Lib"
        )
    else:
        # 其他平台（Linux 等），回退到相对路径
        lib_dir = os.path.normpath(
            os.path.join(script_path, "..", "..", "..","HB", "Translator","Lib")
        )

    # 3. 规范化一下路径（去掉多余分隔符或 ..）
    lib_dir = os.path.normpath(lib_dir)
    # —— 二、插入到 sys.path —— 
    if os.path.isdir(lib_dir):
        # 放到最前面，确保优先加载
        sys.path.insert(0, lib_dir)
    else:
        # 如果路径不对，可打印日志帮助调试
        print(f"Warning: TTS/Lib directory doesn’t exist.：{lib_dir}", file=sys.stderr)

    try:
        import requests
        from deep_translator import GoogleTranslator
        print(lib_dir)
    except ImportError as e:
        print("依赖导入失败，请确保所有依赖已打包至 Lib 目录中：", lib_dir, "\n错误信息：", e)

RAND_CODE = "".join(random.choices(string.digits, k=2))

script_path       = os.path.dirname(os.path.abspath(sys.argv[0]))
config_dir        = os.path.join(script_path, "config")
settings_file     = os.path.join(config_dir, "translator_settings.json")
custom_models_file = os.path.join(config_dir, "models.json")
status_file = os.path.join(config_dir, 'status.json')

class STATUS_MESSAGES:
    pass
with open(status_file, "r", encoding="utf-8") as file:
    status_data = json.load(file)
for key, (en, zh) in status_data.items():
    setattr(STATUS_MESSAGES, key, (en, zh))
# =============== Provider 抽象层 ===============
class BaseProvider(ABC):
    name: str = "base"
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.initialized = False

    def initialize(self, text: str, target_lang: str):
        """Perform a test translation to ensure the provider works"""
        if not self.initialized:
            result = self.translate(text, target_lang)
            self.initialized = True
            return result
        return None
    @abstractmethod
    def translate(self, text: str, target_lang: str, *args, **kwargs) -> str: ...

# -- Google -------------------------------
class GoogleProvider(BaseProvider):
    name = GOOGLE_PROVIDER

    def __init__(self, cfg):
        super().__init__(cfg)
        # deep_translator 不需要预先实例化 translator

    def translate(self, text, target_lang):
        """
        target_lang: deep_translator 接受的语言代码，例如 'zh-cn' 或 'en'
        """
        for attempt in range(1, self.cfg.get("max_retry", 3) + 1):
            try:
                # 每次调用时根据目标语言新建一个 GoogleTranslator 实例
                translator = GoogleTranslator(source='auto', target=target_lang)
                return translator.translate(text)
            except Exception as e:
                if attempt == self.cfg.get("max_retry", 3):
                    raise
                time.sleep(2 ** attempt)


# -- Microsoft ----------------------------
class AzureProvider(BaseProvider):
    name = AZURE_PROVIDER
    def translate(self, text, target_lang):
        params  = {"api-version": "3.0", "to": target_lang}
        headers = {
            "Ocp-Apim-Subscription-Key": self.cfg["api_key"],
            "Ocp-Apim-Subscription-Region": self.cfg["region"],
            "Content-Type": "application/json"
        }
        url  = self.cfg["base_url"].rstrip("/") + "/translate"
        body = [{"text": text}]

        for attempt in range(1, self.cfg.get("max_retry", 3)+1):
            try:
                r = requests.post(url, params=params, headers=headers,
                                  json=body, timeout=self.cfg.get("timeout", 15))
                r.raise_for_status()
                return r.json()[0]["translations"][0]["text"]
            except Exception as e:
                if attempt == self.cfg.get("max_retry", 3):
                    raise
                time.sleep(2 ** attempt)
                
# -- AI Translator ------------------------
class AITranslatorProvider(BaseProvider):
    name = AI_PROVIDER

    def translate(self, text, target_lang, prefix: str = "", suffix: str = ""):
        """
        text   : 当前待译行
        prefix : 上下文前文（可为空）
        suffix : 上下文后文（可为空）
        """
        # ---------- 1 组织用户消息 ----------
        user_msg_parts = []
        if prefix:
            user_msg_parts.append("<<< CONTEXT (above) >>>\n" + prefix)
        if suffix:
            user_msg_parts.append("<<< CONTEXT (below) >>>\n" + suffix)
        # 当前句一定要放最后，避免模型遗漏
        user_msg_parts.append("<<< Please translate the following sentence >>>\n"
                            + text)
        user_content = "\n\n".join(user_msg_parts)

        # ---------- 2 ChatCompletion payload ----------
        prompt_content = SYSTEM_PROMPT.format(
            target_lang=f"{{{target_lang}}}"
         )
        #print(prompt_content)
        payload = {
            "model": self.cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": prompt_content
                    
                },
                {"role": "user", "content": user_content}
            ],
            "temperature": 0
        }
        headers = {
            "Authorization": f"Bearer {self.cfg['api_key']}",
            "Content-Type": "application/json"
        }
        url = self.cfg["base_url"].rstrip("/") + "/v1/chat/completions"

        # ---------- 3 带指数退避的重试 ----------
        for attempt in range(1, self.cfg.get("max_retry", 3) + 1):
            try:
                r = requests.post(
                    url, headers=headers, json=payload,
                    timeout=self.cfg.get("timeout", 30)
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                if attempt == self.cfg.get("max_retry", 3):
                    raise
                time.sleep(2 ** attempt)




# =============== Provider 管理器 ===============
class ProviderManager:
    def __init__(self, cfg: dict):
        self._providers = {}
        self.default = cfg.get("default")
        for name, p_cfg in cfg["providers"].items():
            cls = globals()[p_cfg["class"]]      # 直接从当前模块拿类
            self._providers[name] = cls(p_cfg)
    def list(self):            # 返回支持的服务商列表
        return list(self._providers.keys())
    def get(self, name=None):  # 获取指定服务商实例
        return self._providers[name or self.default]
    
    def update_cfg(self, name: str, **new_cfg):
        if name not in self._providers:
            raise ValueError("Provider 不存在，无法更新配置")
        # 重建实例以应用最新配置
        cls = self._providers[name].__class__
        cfg = {**self._providers[name].cfg, **new_cfg}
        self._providers[name] = cls(cfg)

# --------- 3  服务商配置（可在 GUI 动态修改后写回） ---------
PROVIDERS_CFG = {
    "default": GOOGLE_PROVIDER,
    "providers": {
        GOOGLE_PROVIDER: {               # ← 新增
            "class": "GoogleProvider",
            "service_urls": [
                "translate.google.com",
                "translate.google.com.hk",
                "translate.google.com.tw"],  # 可多填备用域名
            "max_retry": MAX_RETRY,
            "timeout": 10
        },
        AZURE_PROVIDER: {
            "class":  "AzureProvider",
            "base_url": AZURE_DEFAULT_URL,
            "api_key":  AZURE_DEFAULT_KEY,
            "region":   AZURE_DEFAULT_REGION,
            "max_retry": MAX_RETRY,
            "timeout":  15
        },
        AI_PROVIDER: {
            "class": "AITranslatorProvider",
            "base_url": OPENAI_DEFAULT_URL,
            "api_key":  OPENAI_DEFAULT_KEY,
            "model":    OPENAI_DEFAULT_MODEL,
            "max_retry": MAX_RETRY,
            "timeout":  TIMEOUT
        },
    }
}

prov_manager = ProviderManager(PROVIDERS_CFG)   # 实例化

# ================== DaVinci Resolve 接入 ==================
try:
    import DaVinciResolveScript as dvr_script
    from python_get_resolve import GetResolve
except ImportError:
    # mac / windows 常规路径补全
    if platform.system() == "Darwin": 
        path1 = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Examples"
        path2 = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
    elif platform.system() == "Windows":
        path1 = os.path.join(os.environ['PROGRAMDATA'], "Blackmagic Design", "DaVinci Resolve", "Support", "Developer", "Scripting", "Examples")
        path2 = os.path.join(os.environ['PROGRAMDATA'], "Blackmagic Design", "DaVinci Resolve", "Support", "Developer", "Scripting", "Modules")
    else:
        raise EnvironmentError("Unsupported operating system")
    sys.path += [path1, path2]
    import DaVinciResolveScript as dvr_script
    from python_get_resolve import GetResolve

resolve = GetResolve()
ui       = fusion.UIManager
dispatcher = bmd.UIDispatcher(ui)

# -------------------- 4  GUI 搭建 --------------------
win = dispatcher.AddWindow(
    {
        "ID": 'MyWin',
        "WindowTitle": SCRIPT_NAME + SCRIPT_VERSION,
        "Geometry": [X_CENTER, Y_CENTER, WINDOW_WIDTH, WINDOW_HEIGHT],
        "Spacing": 10,
        "StyleSheet": "*{font-size:14px;}"
    },
    [
        ui.VGroup([
            ui.TabBar({"ID":"MyTabs","Weight":0.0}),
            ui.Stack({"ID":"MyStack","Weight":1.0},[
                # ===== 4.1 翻译页 =====
                ui.VGroup({"Weight":1},[
                    ui.Label({"ID":"TargetLangLabel","Text":"目标语言","Weight":0.1}),
                    ui.ComboBox({"ID":"TargetLangCombo","Weight":0.1}),
                    ui.Label({"ID": "StatusLabel", "Text": " ", "Alignment": {"AlignHCenter": True, "AlignVCenter": True},"Weight":0.1}),
                    ui.Button({"ID":"TransButton","Text":"翻译","Weight":0.1}),
                    #ui.TextEdit({"ID":"SubTxt","Text":"","ReadOnly":False,"Weight":0.8}),
                ]),
                # ===== 4.2 配置页 =====
                ui.VGroup({"Weight":1},[
                    ui.Label({"ID":"ProviderLabel","Text":"服务商","Weight":0.1}),
                    ui.ComboBox({"ID":"ProviderCombo","Weight":0.1}),
                    ui.HGroup({"Weight": 0.1}, [
                        ui.Label({"ID":"MicrosoftConfigLabel","Text": "Microsoft", "Alignment": {"AlignLeft": True}, "Weight": 0.1}),
                        ui.Button({"ID": "ShowAzure", "Text": "配置","Weight": 0.1,}),
                    ]),
                    ui.HGroup({"Weight":0.1},[
                        ui.Label({"ID":"AIConfigLabel","Text":"AI Translator","Weight":0.1}),
                        ui.Button({"ID":"ShowAITranslator","Text":"配置","Weight":0.1}),
                    ]),
                    ui.Label({"ID":"MoreScriptLabel","Text":"","Weight":0.1,"Alignment": {"AlignHCenter": True, "AlignVCenter": True}}),
                    ui.Button({"ID":"TTSButton","Text":"文字转语音插件","Weight":0.1}),
                    ui.HGroup({"Weight":0.1},[
                        ui.CheckBox({"ID":"LangEnCheckBox","Text":"EN","Checked":True,"Weight":0}),
                        ui.CheckBox({"ID":"LangCnCheckBox","Text":"简体中文","Checked":False,"Weight":1}),
                    ]),
                    #ui.TextEdit({"ID":"infoTxt","Text":"","ReadOnly":True,"Weight":1}),
                    #ui.Label({"ID":"CopyrightLabel","Text":f"© 2025, Copyright by {SCRIPT_AUTHOR}","Weight":0.1,"Alignment": {"AlignHCenter": True, "AlignVCenter": True}}),
                    ui.Button({
                            "ID": "CopyrightButton", 
                            "Text": f"© 2025, Copyright by {SCRIPT_AUTHOR}",
                            "Alignment": {"AlignHCenter": True, "AlignVCenter": True},
                            "Font": ui.Font({"PixelSize": 12, "StyleName": "Bold"}),
                            "Flat": True,
                            "TextColor": [0.1, 0.3, 0.9, 1],
                            "BackgroundColor": [1, 1, 1, 0],
                            "Weight": 0
                        })
                ])
            ])
        ])
    ]
)

# --- OpenAI 单独配置窗口（维持原有） ---
# openai配置窗口
ai_config_window = dispatcher.AddWindow(
    {
        "ID": "AITranslatorConfigWin",
        "WindowTitle": "AI Translator API",
        "Geometry": [750, 400, 400, 300],
        "Hidden": True,
        "StyleSheet": """
        * {
            font-size: 14px; /* 全局字体大小 */
        }
    """
    },
    [
        ui.VGroup(
            [
                ui.Label({"ID": "OpenAILabel","Text": "填写AI Translator 信息", "Alignment": {"AlignHCenter": True, "AlignVCenter": True},"Weight": 0.1}),
                ui.Label({"ID":"OpenAIModelLabel","Text":"模型","Weight":0.1}),
                ui.ComboBox({"ID":"OpenAIModelCombo","Weight":0.2}),  
                ui.Label({"ID": "NewModelNameLabel", "Text": "* Model name"}),
                ui.LineEdit({"ID": "NewModelName", "ReadOnly":True, "Text": ""}),
                ui.Label({"ID": "NewBaseURLLabel", "Text": "* Base URL"}),
                ui.LineEdit({"ID": "NewBaseURL", "ReadOnly":True, "Text": ""}),
                ui.Label({"ID": "NewApiKeyLabel", "Text": "* API Key"}),
                ui.LineEdit({"ID": "NewApiKey", "Text": "", "ReadOnly":True, "EchoMode": "Password"}),
                ui.HGroup({"Weight": 0.15}, [
                    ui.Button({"ID": "ShowAddModel", "Text": "新增模型","Weight": 1}),
                    ui.Button({"ID": "ShowEditModel", "Text": "注册","Weight": 1}),
                ]),
                
                #ui.Label({"ID":"SystemPromptLabel","Text":"提示词：","Weight":0.1}),
                #ui.TextEdit({"ID":"SystemPromptTxt","Text": f"<span style='color:#f59b37;font-size:16px;'>{SYSTEM_PROMPT}</span>","ReadOnly":True,"Weight":1}), 
                
                
            ]
        )
    ]
)

# azure配置窗口
azure_config_window = dispatcher.AddWindow(
    {
        "ID": "AzureConfigWin",
        "WindowTitle": "Microsoft API",
        "Geometry": [750, 400, 400, 200],
        "Hidden": True,
        "StyleSheet": """
        * {
            font-size: 14px; /* 全局字体大小 */
        }
    """
    },
    [
        ui.VGroup(
            [
                ui.Label({"ID": "AzureLabel","Text": "Azure API", "Alignment": {"AlignHCenter": True, "AlignVCenter": True}}),
                ui.HGroup({"Weight": 1}, [
                    ui.Label({"ID": "AzureRegionLabel", "Text": "区域", "Alignment": {"AlignRight": False}, "Weight": 0.2}),
                    ui.LineEdit({"ID": "AzureRegion", "Text": "", "Weight": 0.8}),
                ]),
                ui.HGroup({"Weight": 1}, [
                    ui.Label({"ID": "AzureApiKeyLabel", "Text": "密钥", "Alignment": {"AlignRight": False}, "Weight": 0.2}),
                    ui.LineEdit({"ID": "AzureApiKey", "Text": "", "EchoMode": "Password", "Weight": 0.8}),
                    
                ]),
                ui.HGroup({"Weight": 1}, [
                    ui.Button({"ID": "AzureConfirm", "Text": "确定","Weight": 1}),
                    ui.Button({"ID": "AzureRegisterButton", "Text": "注册","Weight": 1}),
                ]),
                
            ]
        )
    ]
)
add_model_window = dispatcher.AddWindow(
    {
        "ID": "AddModelWin",
        "WindowTitle": "Add Model",
        "Geometry": [750, 400, 300, 400],
        "Hidden": True,
        "StyleSheet": "*{font-size:14px;}"
    },
    [
        ui.VGroup([
            ui.Label({"ID": "AddModelTitle", "Text": "添加 OpenAI 兼容模型", "Alignment": {"AlignHCenter": True, "AlignVCenter": True}}),
            ui.Label({"ID": "NewModelDisplayLabel", "Text": "Display name"}),
            ui.LineEdit({"ID": "NewModelDisplay", "Text": ""}),
            ui.Label({"ID": "NewModelNameLabel", "Text": "* Model name"}),
            ui.LineEdit({"ID": "NewModelName", "Text": ""}),
            ui.Label({"ID": "NewBaseURLLabel", "Text": "* Base URL"}),
            ui.LineEdit({"ID": "NewBaseURL", "Text": ""}),
            ui.Label({"ID": "NewApiKeyLabel", "Text": "* API Key"}),
            ui.LineEdit({"ID": "NewApiKey", "Text": "", "EchoMode": "Password"}),
            ui.Label({"ID": "VerifyStatus", "Text": "", "Alignment": {"AlignHCenter": True}}),
            ui.HGroup([
                ui.Button({"ID": "VerifyModel", "Text": "Verify"}),
                ui.Button({"ID": "AddModelBtn", "Text": "Add Model"}),
            ])
        ])
    ]
)
msgbox = dispatcher.AddWindow(
        {
            "ID": 'msg',
            "WindowTitle": 'Warning',
            "Geometry": [750, 400, 350, 100],
            "Spacing": 10,
        },
        [
            ui.VGroup(
                [
                    ui.Label({"ID": 'WarningLabel', "Text": ""}),
                    ui.HGroup(
                        {
                            "Weight": 0,
                        },
                        [
                            ui.Button({"ID": 'OkButton', "Text": 'OK'}),
                        ]
                    ),
                ]
            ),
        ]
    )

def show_warning_message(status_tuple):
    use_english = items["LangEnCheckBox"].Checked
    # 元组索引 0 为英文，1 为中文
    message = status_tuple[0] if use_english else status_tuple[1]
    msgbox.Show()
    msg_items["WarningLabel"].Text = message

def on_msg_close(ev):
    msgbox.Hide()
msgbox.On.OkButton.Clicked = on_msg_close
msgbox.On.msg.Close = on_msg_close


translations = {
    "cn": {
        "Tabs": ["翻译","配置"],
        "OpenAIModelLabel":"选择模型：",
        "TargetLangLabel":"目标语音：",
        "TransButton":"开始翻译",
        "MicrosoftConfigLabel":"Microsoft",
        "ShowAzure":"配置",
        "ShowAITranslator": "配置",
        "MoreScriptLabel":"\n———————————更多功能———————————",
        "TTSButton":"文字转语音（TTS）插件",
        "ProviderLabel":"服务商",
        "AzureRegionLabel":"区域",
        "AzureApiKeyLabel":"密钥",
        "AzureConfirm":"确定",
        "AzureRegisterButton":"注册",
        "AzureLabel":"填写Azure API信息",
        "OpenAILabel":"填写OpenAI Format API信息",
        "ShowAddModel":"新增模型",
        "ShowEditModel":"编辑模型",
        "VerifyModel":"验证",
        "AddModelTitle":"添加 OpenAI 兼容模型",
        "NewModelNameLabel":"* 模型",
        "NewModelDisplayLabel":"名称",
        "AddModelBtn":"添加",
        
        
    },

    "en": {
        "Tabs": ["Translator", "Configuration"],
        "OpenAIModelLabel":"Select Model:",
        "TargetLangLabel":"Target Language:",
        "TransButton":"Translate",
        "MicrosoftConfigLabel":"Microsoft",
        "ShowAzure":"Config",
        "ShowAITranslator": "Config",
        "MoreScriptLabel":"\n—————————MORE FEATURES—————————",
        "TTSButton":"Text to Speech (TTS) Script",
        "ProviderLabel":"Provider",
        "AzureRegionLabel":"Region",
        "AzureApiKeyLabel":"Key",
        "AzureConfirm":"OK",
        "AzureRegisterButton":"Register",
        "AzureLabel":"Azure API",
        "OpenAILabel":"OpenAI Format API",
        "ShowAddModel":"Add Model",
        "ShowEditModel":"Edit Model",
        "AddModelTitle":"Add OpenAI Format Model",
        "NewModelNameLabel":"* Model name",
        "NewModelDisplayLabel":"Display name",
        "VerifyModel":"Verify",
        "AddModelBtn":"Add",
        
        
    }
}    

items       = win.GetItems()
openai_items = ai_config_window.GetItems()
azure_items = azure_config_window.GetItems()
add_model_items = add_model_window.GetItems()
msg_items = msgbox.GetItems()
items["MyStack"].CurrentIndex = 0

# --- 4.3 初始化下拉内容 ---
for tab_name in translations["cn"]["Tabs"]:
    items["MyTabs"].AddTab(tab_name)


target_language = [
    "中文（普通话）", "中文（粤语）", "English", "Japanese", "Korean",
    "Spanish", "Portuguese", "French", "Indonesian", "German", "Russian",
    "Italian", "Arabic", "Turkish", "Ukrainian", "Vietnamese", "Dutch"
]

for lang in target_language:
    items["TargetLangCombo"].AddItem(lang)
    
def check_or_create_file(file_path):
    if os.path.exists(file_path):
        pass
    else:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as file:
                json.dump({}, file)
        except IOError:
            raise Exception(f"Cannot create file: {file_path}")
        
def save_settings(settings, settings_file):
    with open(settings_file, 'w') as file:
        content = json.dumps(settings, indent=4)
        file.write(content)
        
def load_settings(settings_file):
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as file:
            content = file.read()
            if content:
                try:
                    settings = json.loads(content)
                    return settings
                except json.JSONDecodeError as err:
                    print('Error decoding settings:', err)
                    return None
    return None

default_settings = {
    "AZURE_API_KEY":"",
    "AZURE_REGION":"",
    "OPENAI_API_KEY": "",
    "PROVIDER":0,
    "OPENAI_BASE_URL": "",
    "OPENAI_MODEL": 0,
    "TARGET_LANG":0,
    "CN":True,
    "EN":False,
}

check_or_create_file(settings_file)
check_or_create_file(custom_models_file)
saved_settings = load_settings(settings_file) 
custom_models = load_settings(custom_models_file)    # {"models": {disp: {...}}}


for p in prov_manager.list():
    items["ProviderCombo"].AddItem(p)

# 预装官方模型
for disp ,info in custom_models.get("models", {}).items():
    openai_items["OpenAIModelCombo"].AddItem(disp)


# 加载用户自定义
for disp ,info in custom_models.get("custom_models", {}).items():
    openai_items["OpenAIModelCombo"].AddItem(disp)



def switch_language(lang):
    """
    根据 lang (可取 'cn' 或 'en') 切换所有控件的文本
    """
    if "MyTabs" in items:
        for index, new_name in enumerate(translations[lang]["Tabs"]):
            items["MyTabs"].SetTabText(index, new_name)

    for item_id, text_value in translations[lang].items():
        # 确保 items[item_id] 存在，否则会报 KeyError
        if item_id == "Tabs":
            continue
        if item_id in items:
            items[item_id].Text = text_value
        elif item_id in azure_items:    
            azure_items[item_id].Text = text_value
        elif item_id in openai_items:    
            openai_items[item_id].Text = text_value
        elif item_id in add_model_items:    
            add_model_items[item_id].Text = text_value
        else:
            print(f"[Warning] items 中不存在 ID 为 {item_id} 的控件，无法设置文本！")

    # 缓存复选框状态
    checked = items["LangEnCheckBox"].Checked



def on_cn_checkbox_clicked(ev):
    items["LangEnCheckBox"].Checked = not items["LangCnCheckBox"].Checked
    if items["LangEnCheckBox"].Checked:
        switch_language("en")
        print("en")
    else:
        print("cn")
        switch_language("cn")
win.On.LangCnCheckBox.Clicked = on_cn_checkbox_clicked

def on_en_checkbox_clicked(ev):
    items["LangCnCheckBox"].Checked = not items["LangEnCheckBox"].Checked
    if items["LangEnCheckBox"].Checked:
        switch_language("en")
        print("en")
    else:
        print("cn")
        switch_language("cn")
win.On.LangEnCheckBox.Clicked = on_en_checkbox_clicked


if saved_settings:
    openai_items["OpenAIModelCombo"].CurrentIndex = saved_settings.get("OPENAI_MODEL", default_settings["OPENAI_MODEL"])
    items["TargetLangCombo"].CurrentIndex = saved_settings.get("TARGET_LANG", default_settings["TARGET_LANG"])
    items["LangCnCheckBox"].Checked = saved_settings.get("CN", default_settings["CN"])
    items["LangEnCheckBox"].Checked = saved_settings.get("EN", default_settings["EN"])
    items["ProviderCombo"].CurrentIndex = saved_settings.get("PROVIDER", default_settings["PROVIDER"])
    azure_items["AzureApiKey"].Text = saved_settings.get("AZURE_API_KEY", default_settings["AZURE_API_KEY"])
    azure_items["AzureRegion"].Text = saved_settings.get("AZURE_REGION", default_settings["AZURE_REGION"])

if items["LangEnCheckBox"].Checked :
    switch_language("en")
else:
    switch_language("cn")

def close_and_save(settings_file):
    settings = {

        "CN":items["LangCnCheckBox"].Checked,
        "EN":items["LangEnCheckBox"].Checked,
        "PROVIDER":items["ProviderCombo"].CurrentIndex,
        "AZURE_API_KEY":azure_items["AzureApiKey"].Text,
        "AZURE_REGION":azure_items["AzureRegion"].Text,
        "OPENAI_MODEL": openai_items["OpenAIModelCombo"].CurrentIndex,
        "TARGET_LANG":items["TargetLangCombo"].CurrentIndex,


    }

    save_settings(settings, settings_file)
# --- 4.4 Tab 切换 ---
def on_my_tabs_current_changed(ev):
    items["MyStack"].CurrentIndex = ev["Index"]
win.On.MyTabs.CurrentChanged = on_my_tabs_current_changed

# --- 4.5 打开 OpenAI 配置窗 ---
def on_show_openai(ev):
    ai_config_window.Show()
win.On.ShowAITranslator.Clicked = on_show_openai

def on_openai_close(ev):
    print("OpenAI Format API setup is complete.")
    ai_config_window.Hide()
ai_config_window.On.AITranslatorConfigWin.Close = on_openai_close


# --- 4.6 打开 Azure 配置窗 ---
def on_show_azure(ev):
    azure_config_window.Show()
win.On.ShowAzure.Clicked = on_show_azure

def on_azure_close(ev):
    print("Azure API setup is complete.")
    azure_config_window.Hide()
azure_config_window.On.AzureConfirm.Clicked = on_azure_close
azure_config_window.On.AzureConfigWin.Close = on_azure_close

def on_azure_register_link_button_clicked(ev):
    ...
azure_config_window.On.AzureRegisterButton.Clicked = on_azure_register_link_button_clicked

def on_tts_button(ev):
    if items["LangEnCheckBox"].Checked :
        webbrowser.open(TTS_KOFI_URL)
    else :
        webbrowser.open(TTS_TAOBAO_URL)
win.On.TTSButton.Clicked = on_tts_button

def on_open_link_button_clicked(ev):
    if items["LangEnCheckBox"].Checked :
        webbrowser.open(SCRIPT_KOFI_URL)
    else :
        webbrowser.open(SCRIPT_BILIBILI_URL)
win.On.CopyrightButton.Clicked = on_open_link_button_clicked

# --- 新增模型弹窗 ---
def on_show_add_model(ev):

    add_model_items["NewModelDisplay"].Text = ""
    add_model_items["NewModelName"].Text    = ""
    add_model_items["NewBaseURL"].Text      = ""
    add_model_items["NewApiKey"].Text       = ""
    ai_config_window.Hide()
    add_model_window.Show()
ai_config_window.On.ShowAddModel.Clicked = on_show_add_model

def on_show_edit_model(ev):
    disp = openai_items["OpenAIModelCombo"].CurrentText
    info = custom_models.get("models", {}).get(disp, {})
    add_model_items["NewModelDisplay"].Text = disp
    add_model_items["NewModelName"].Text    = info.get("model", disp)
    add_model_items["NewBaseURL"].Text      = info.get("base_url", "")
    add_model_items["NewApiKey"].Text       = info.get("api_key", "")
    ai_config_window.Hide()
    add_model_window.Show()
ai_config_window.On.ShowEditModel.Clicked = on_show_edit_model

def verify_settings(base_url, api_key, model):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = base_url.rstrip("/") + "/v1/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return True, ""
    except Exception as e:
        return False, str(e)

def on_verify_model(ev):
    model = add_model_items["NewModelName"].Text.strip()
    base = add_model_items["NewBaseURL"].Text.strip()
    key = add_model_items["NewApiKey"].Text.strip()
    ok, msg = verify_settings(base, key, model)
    add_model_items["VerifyStatus"].Text = "OK" if ok else f"Failed: {msg}"

def on_add_model(ev):
    # === 0 读取输入 ===
    model    = add_model_items["NewModelName"].Text.strip()
    display  = add_model_items["NewModelDisplay"].Text.strip() or model
    base_url = add_model_items["NewBaseURL"].Text.strip()
    api_key  = add_model_items["NewApiKey"].Text.strip()
    if not (model or display or base_url or api_key):
        add_model_items["VerifyStatus"].Text = "参数错误" # 或者使用 UI 元素显示错误
        return
    # === 1 取两张表的引用，若不存在先建空表 ===
    models_tbl = custom_models.setdefault("models", {})          # 预装或已验证过的模型
    custom_tbl = custom_models.setdefault("custom_models", {})   # 用户自定义

    # === 2 先在两张表里查重：按「显示名」或「模型名」 ===
    updated = False
    for tbl in (models_tbl, custom_tbl):
        # A. 显示名已存在
        if display in tbl:
            entry = tbl[display]
        # B. 其它条目的 model 与输入 model 同名
        elif any(v.get("model") == model for v in tbl.values()):
            # 找到第一个匹配项并使用其 key
            key = next(k for k, v in tbl.items() if v.get("model") == model)
            entry = tbl[key]
            display = key     # 统一使用已存在的显示名
        else:
            continue          # 本张表无匹配 → 下一张表
        # 覆盖已存在字段（留空的不覆盖）
        if model:    entry["model"]    = model
        if base_url: entry["base_url"] = base_url
        if api_key:  entry["api_key"]  = api_key
        updated = True

    # === 3 若两张表都未命中 → 视作新增 ===
    if not updated:
        custom_tbl[display] = {
            "model":    model,
            "base_url": base_url,
            "api_key":  api_key,
        }
        # 只在真正新增时才插入下拉框，避免重复
        openai_items["OpenAIModelCombo"].AddItem(display)

    # === 4 持久化写回 ===
    save_settings(custom_models, custom_models_file)
    # === 5 关闭当前窗口，回到主配置窗口 ===
    ai_config_window.Show()
    add_model_window.Hide()

add_model_window.On.VerifyModel.Clicked = on_verify_model
add_model_window.On.AddModelBtn.Clicked = on_add_model

def on_openai_model_changed(ev):
    """
    当 OpenAIModelCombo 选中项发生变化时，
    实时更新 NewModelName、NewBaseURL、NewApiKey 的显示内容。
    """
    # 1. 获取下拉框当前显示名
    disp = openai_items["OpenAIModelCombo"].CurrentText
    print(disp)

    # 2. 从 custom_models 中查询：优先查“自定义”表，否则查“预装”表
    entry = (
        custom_models.get("custom_models", {}).get(disp)
        or custom_models.get("models", {}).get(disp)
    )

    # 3. 如果找到了 dict，就更新对应字段；否则清空或回退
    if isinstance(entry, dict):
        openai_items["NewModelName"].PlaceholderText = entry.get("model", "")
        openai_items["NewBaseURL"].PlaceholderText = entry.get("base_url", "")
        openai_items["NewApiKey"].PlaceholderText  = entry.get("api_key", "")
    else:
        # 无配置时可清空，也可回退到默认
        openai_items["NewModelName"].PlaceholderText = ""
        openai_items["NewBaseURL"].PlaceholderText = ""
        openai_items["NewApiKey"].PlaceholderText  = ""

# 4. 绑定事件：ComboBox 的 CurrentIndexChanged
ai_config_window.On.OpenAIModelCombo.CurrentIndexChanged = on_openai_model_changed
# =============== 5  Resolve 辅助函数 ===============
def connect_resolve():
    resolve = dvr_script.scriptapp("Resolve")
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    media_pool = project.GetMediaPool(); 
    root_folder = media_pool.GetRootFolder()
    timeline      = project.GetCurrentTimeline()
    fps     = float(project.GetSetting("timelineFrameRate"))
    return resolve, project, media_pool,root_folder,timeline, fps

def get_subtitles(timeline):
    subs = []
    for tidx in range(1, timeline.GetTrackCount("subtitle")+1):
        if not timeline.GetIsTrackEnabled("subtitle", tidx):
            continue
        for item in timeline.GetItemListInTrack("subtitle", tidx):
            subs.append({"start":item.GetStart(),
                         "end":item.GetEnd(),
                         "text":item.GetName()})
    return subs

def frame_to_timecode(frame, fps):
    sec      = frame / fps
    h, rem   = divmod(sec, 3600)
    m, rem   = divmod(rem, 60)
    s, msec  = divmod(rem, 1)
    return f"{int(h):02}:{int(m):02}:{int(s):02},{int(msec*1000):03}"

def write_srt(subs, start_frame, fps, timeline_name, lang_code, output_dir="."):
    """
    按 [时间线名称]_[语言code]_[月日时分]_[4位随机码]_[版本].srt 规则写文件：
      1. 安全化时间线名称和语言code
      2. 获取当前时间戳（月日时分）
      3. 扫描已有文件，计算新版本号
      4. 写入并返回路径
    """
    # 1. 安全化名称
    safe_name = re.sub(r'[\\\/:*?"<>|]', "_", timeline_name)
    safe_lang = re.sub(r'[\\\/:*?"<>|]', "_", lang_code)
    from datetime import datetime
    # 2. 获取当前时间戳（月日时分），格式化为 MMDDHHMM
    timestamp = datetime.now().strftime("%m%d%H%M")

    # 3. 创建目录（若不存在）
    os.makedirs(output_dir, exist_ok=True)

    # 4. 扫描已有版本：匹配形如
    #    safe_name_safe_lang_（任意8位数字）_RAND_CODE_版本.srt
    pattern = re.compile(
        rf"^{re.escape(safe_name)}_{re.escape(safe_lang)}_\d{{8}}_{re.escape(RAND_CODE)}_(\d+)\.srt$"
    )
    versions = []
    for fname in os.listdir(output_dir):
        m = pattern.match(fname)
        if m:
            versions.append(int(m.group(1)))
    version = max(versions) + 1 if versions else 1

    # 5. 构造文件名与路径
    filename = f"{safe_name}_{safe_lang}_{timestamp}_{RAND_CODE}_{version}.srt"
    path = os.path.join(output_dir, filename)

    # 6. 写入 SRT 内容
    with open(path, "w", encoding="utf-8") as f:
        for idx, s in enumerate(subs, 1):
            f.write(
                f"{idx}\n"
                f"{frame_to_timecode(s['start'] - start_frame, fps)} --> "
                f"{frame_to_timecode(s['end']   - start_frame, fps)}\n"
                f"{s['text']}\n\n"
            )

    return path

def import_srt_to_first_empty(path):
    resolve, current_project,current_media_pool,current_root_folder, current_timeline, fps = connect_resolve()
    if not current_timeline: return False
    # 1. 禁用所有现有字幕轨
    states = {}
    for i in range(1, current_timeline.GetTrackCount("subtitle")+1):
        states[i] = current_timeline.GetIsTrackEnabled("subtitle", i)
        if states[i]: current_timeline.SetTrackEnable("subtitle", i, False)
    # 2. 找第一条空轨，没有就新建
    target = next((i for i in range(1, current_timeline.GetTrackCount("subtitle")+1)
                   if not current_timeline.GetItemListInTrack("subtitle", i)), None)
    if target is None:
        current_timeline.AddTrack("subtitle")
        target = current_timeline.GetTrackCount("subtitle")
    current_timeline.SetTrackEnable("subtitle", target, True)
    # 3. 导入
    current_media_pool.SetCurrentFolder(current_root_folder)
    current_media_pool.ImportMedia([path])
    current_media_pool.AppendToTimeline([current_root_folder.GetClipList()[-1]])
    print("🎉 The subtitles were inserted into track #", target)
    return True

# =============== 并发翻译封装 ===============
def translate_parallel(texts, provider, target_code,
                       status_label=None, ctx_win=CONTEXT_WINDOW):
    total, done = len(texts), 0
    result = [None]*total
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {}
        for idx, t in enumerate(texts):
            if isinstance(provider, AITranslatorProvider) and ctx_win>0:
                pre = "\n".join(texts[max(0, idx-ctx_win):idx])
                suf = "\n".join(texts[idx+1: idx+1+ctx_win])
                fut = pool.submit(provider.translate, t, target_code, pre, suf)
            else:
                fut = pool.submit(provider.translate, t, target_code)
            futures[fut] = idx
        for f in concurrent.futures.as_completed(futures):
            i = futures[f]
            try: result[i] = f.result()
            except Exception as e: result[i] = f"[失败:{e}]"
            done += 1
            if status_label:
                pct = int(done/total*100)
                status_label.Text = f"翻译中... {pct}% ({done}/{total})"
    return result


# =============== 主按钮逻辑（核心差异处 ★★★） ===============
def on_trans_clicked(ev):
    # 1. 取字幕
    resolve, proj, mpool, root, tl, fps = connect_resolve()
    subs = get_subtitles(tl)
    if not subs:
        show_warning_message(STATUS_MESSAGES.nosub)
        return

    # 2. 确定 Provider & 目标语言
    provider_name = items["ProviderCombo"].CurrentText
    target_lang_name = items["TargetLangCombo"].CurrentText

    # 2.1 如果是 AI_PROVIDER，再根据模型显示名决定真 model
    if provider_name == AI_PROVIDER:
        disp_model = openai_items["OpenAIModelCombo"].CurrentText
        entry = (custom_models.get("custom_models", {}).get(disp_model)
                 or custom_models.get("models", {}).get(disp_model))

        if entry and isinstance(entry, dict):
            # 从 JSON 取得
            real_model = str(entry.get("model") or disp_model).strip()
            base_url   = str(entry.get("base_url") or OPENAI_DEFAULT_URL).strip()
            api_key    = str(entry.get("api_key") or OPENAI_DEFAULT_KEY).strip()
        else:
            # 内置模型 → 仍允许界面覆盖
            real_model = OPENAI_DEFAULT_MODEL
            base_url   = OPENAI_DEFAULT_URL
            api_key    = OPENAI_DEFAULT_KEY

        # 更新 Provider 配置
        prov_manager.update_cfg(AI_PROVIDER,
            model   = real_model,
            base_url= base_url,
            api_key = api_key,
        )
        provider     = prov_manager.get(AI_PROVIDER)
        target_code  = target_lang_name                 # AI 使用全称
    elif provider_name == AZURE_PROVIDER:
        prov_manager.update_cfg(AZURE_PROVIDER,
            api_key = azure_items["AzureApiKey"].Text.strip() or AZURE_DEFAULT_KEY,
            region  = azure_items["AzureRegion"].Text.strip() or AZURE_DEFAULT_REGION,
        )
        provider = prov_manager.get(AZURE_PROVIDER)
        target_code = AZURE_LANG_CODE_MAP[target_lang_name]
    elif provider_name == GOOGLE_PROVIDER:
        provider = prov_manager.get(GOOGLE_PROVIDER)
        target_code = GOOGLE_LANG_CODE_MAP[target_lang_name]
    else:
        items["StatusLabel"].Text = "❌ 未识别的服务商"
        return

    # 3. 并发翻译
    items["TransButton"].Enabled = False
    show_warning_message(STATUS_MESSAGES.initialize)
    try:
        first_result = provider.initialize(subs[0]["text"], target_code)
    except Exception as e:
        show_warning_message(STATUS_MESSAGES.initialize_fault)
        print(f"初始化失败，异常原因：{e}")
        items["TransButton"].Enabled = True
        return
    msgbox.Hide()
    items["StatusLabel"].Text = "翻译中... 0% (0/{})".format(len(subs))

    translated = [first_result] if first_result is not None else []
    if len(subs) > 1:
        pct = int(1/len(subs)*100)
        items["StatusLabel"].Text = f"翻译中... {pct}% (1/{len(subs)})"
        rest = translate_parallel(
            [s["text"] for s in subs[1:]], provider, target_code, items["StatusLabel"]
        )
        translated.extend(rest)
    else:
        items["StatusLabel"].Text = "翻译中... 100% (1/1)"

    for s, new_txt in zip(subs, translated):
        s["text"] = new_txt
    # 4. 写 SRT → 导入
    srt_dir = os.path.join(script_path, "srt")
    srt_path = write_srt(subs, tl.GetStartFrame(), fps,
                         tl.GetName(), target_code, output_dir=srt_dir)
    if import_srt_to_first_empty(srt_path):
        show_warning_message(STATUS_MESSAGES.finished)
        items["StatusLabel"].Text = ""
    else:
        items["StatusLabel"].Text = "⚠️ 导入失败！"

    items["TransButton"].Enabled = True
win.On.TransButton.Clicked = on_trans_clicked

# =============== 8  关闭窗口保存设置 ===============
def on_close(ev):
    import shutil
    output_dir = os.path.join(script_path, 'srt')
    if os.path.exists(output_dir):
        try:
            shutil.rmtree(output_dir)  # ✅ 删除整个文件夹及其中内容
            print(f"🧹 :{output_dir}")
        except Exception as e:
            print(f"⚠️ Failed to delete the dir.：{e}")
    close_and_save(settings_file)
    dispatcher.ExitLoop()

win.On.MyWin.Close = on_close

def on_add_model_close(ev):
    ai_config_window.Show()
    add_model_window.Hide(); 
add_model_window.On.AddModelWin.Close = on_add_model_close
# =============== 9  运行 GUI ===============
win.Show(); 
dispatcher.RunLoop(); 
win.Hide(); 
ai_config_window.Hide()
azure_config_window.Hide()
msgbox.Hide()