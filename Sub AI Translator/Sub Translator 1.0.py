# ================= 用户配置 =================
SCRIPT_NAME    = "Sub AI Translator "
SCRIPT_VERSION = "1.0"
SCRIPT_AUTHOR  = "HEIBA"

SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
WINDOW_WIDTH, WINDOW_HEIGHT = 300, 300
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

OEPANI_FORMAT_API_KEY   = ""
OEPANI_FORMAT_BASE_URL   = "https://api.openai.com"
OPENAI_FORMAT_MODEL = "gpt-4o-mini"
OPENAI_DEFAULT_TEMPERATURE = 0.3


GOOGLE_PROVIDER = "Google"
AZURE_PROVIDER  = "Microsoft (API Key)"
DEEPL_PROVIDER = "DeepL (API Key)"
OPENAI_FORMAT_PROVIDER     = "Open AI Format (API Key)"

AZURE_DEFAULT_KEY    = ""
AZURE_DEFAULT_REGION = ""
AZURE_DEFAULT_URL    = "https://api.cognitive.microsofttranslator.com"
PROVIDER             = 0
DEEPL_DEFAULT_KEY    = ""
CONTEXT_WINDOW = 1
SYSTEM_PROMPT = """
You are a professional subtitle translation engine.

Task: Translate ONLY the sentence shown after the tag <<< Sentence >>> into {target_lang}.

Strict rules you MUST follow:
1. Keep every proper noun, personal name, brand, product name, code snippet, file path, URL, and any other non-translatable element EXACTLY as it appears. Do NOT transliterate or translate these.
2. Follow subtitle style: short, concise, natural, and easy to read.
3. Output ONLY the translated sentence. No tags, no explanations, no extra spaces.

Note:
- The messages with role=assistant are only CONTEXT; do NOT translate them or include them in your output.
- Translate ONLY the line after <<< Sentence >>>.
"""

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
    from deep_translator import DeeplTranslator
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
        from deep_translator import DeeplTranslator
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

def get_machine_id():
        import hashlib
        import subprocess
        import uuid
        system = platform.system()
        # 1. Linux: /etc/machine-id 或 /var/lib/dbus/machine-id
        if system == "Linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.exists(path):
                    try:
                        return open(path, "r", encoding="utf-8").read().strip()
                    except Exception:
                        pass
        # 2. Windows: 注册表 MachineGuid
        elif system == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography"
                )
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
                return value
            except Exception:
                pass
        # 3. macOS: IOPlatformUUID
        elif system == "Darwin":
            try:
                output = subprocess.check_output(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    stderr=subprocess.DEVNULL
                ).decode()
                import re
                m = re.search(r'"IOPlatformUUID" = "([^"]+)"', output)
                if m:
                    return m.group(1)
            except Exception:
                pass

        # 4. 回退：MAC 地址做 SHA256 哈希
        mac = uuid.getnode()
        # uuid.getnode() 不一定保证唯一（虚拟机可能一样），但一般可用
        return hashlib.sha256(str(mac).encode("utf-8")).hexdigest()
global USERID 
USERID = get_machine_id()
# -- Microsoft ----------------------------
class AzureProvider(BaseProvider):
    name = AZURE_PROVIDER
    def translate(self, text, target_lang):
        # -------- 1. 读取配置 --------
        api_key = self.cfg.get("api_key", "").strip()
        region  = self.cfg.get("region", "").strip()

        # -------- 2A. 走 Azure 官方翻译 --------
        if api_key and region:
            params = {"api-version": "3.0", "to": target_lang}
            headers = {
                "Ocp-Apim-Subscription-Key": api_key,
                "Ocp-Apim-Subscription-Region": region,
                "Content-Type": "application/json"
            }
            url  = (self.cfg.get("base_url") or AZURE_DEFAULT_URL).rstrip("/") + "/translate"
            body = [{"text": text}]

            for attempt in range(1, self.cfg.get("max_retry", 3) + 1):
                try:
                    r = requests.post(url, params=params, headers=headers,
                                      json=body, timeout=self.cfg.get("timeout", 15))
                    r.raise_for_status()
                    return r.json()[0]["translations"][0]["text"]
                except Exception as e:
                    if attempt == self.cfg.get("max_retry", 3):
                        raise
                    time.sleep(2 ** attempt)

        # -------- 2B. 否则走 Dify workflow --------
        headers = {
            "Authorization": "Bearer app-vol8lkhuewkHvLGL0rnSaZ5L",
            "Content-Type":  "application/json"
        }
        url = "http://118.89.121.18/v1/workflows/run"
        payload = {
            "inputs": {
                "text": text,
                "target_lang": target_lang
            },
            "user": USERID,                # 固定机器 ID
            "response_mode": "blocking"
        }

        for attempt in range(1, self.cfg.get("max_retry", 3) + 1):
            try:
                r = requests.post(url, headers=headers,
                                  json=payload, timeout=self.cfg.get("timeout", 15))
                r.raise_for_status()
                resp = r.json()
                outputs = resp.get("data", {}).get("outputs", {})
                if "result" not in outputs:
                    raise ValueError(
                        "Dify 返回中找不到 'result' 字段：\n"
                        + json.dumps(resp, indent=2, ensure_ascii=False)
                    )
                return outputs["result"]
            except Exception as e:
                if attempt == self.cfg.get("max_retry", 3):
                    raise
                time.sleep(2 ** attempt)


# -- DeepL ------------------------                
class DeepLProvider(BaseProvider):
    name = DEEPL_PROVIDER

    def translate(self, text, target_lang):
        for attempt in range(1, self.cfg.get("max_retry", 3) + 1):
            try:
                translator = DeeplTranslator(
                    source='auto',
                    target=target_lang,
                    api_key=self.cfg.get("api_key", "")
                )
                return translator.translate(text)
            except Exception:
                if attempt == self.cfg.get("max_retry", 3):
                    raise
                time.sleep(2 ** attempt)
# -- AI Translator ------------------------
class OpenAIFormatProvider(BaseProvider):
    _session = requests.Session()
    name = OPENAI_FORMAT_PROVIDER

    def translate(self, text, target_lang, prefix: str = "", suffix: str = ""):
        """
        返回: (翻译文本, usage dict)
        usage 包含 'prompt_tokens', 'completion_tokens', 'total_tokens'
        """
        prompt_content = SYSTEM_PROMPT.format(target_lang=target_lang)

        messages = [{"role": "system", "content": prompt_content}]
        # 上下文
        ctx = "\n".join(filter(None, [prefix, suffix]))
        if ctx:
            messages.append({"role": "assistant", "content": ctx})
        messages.append({"role": "user", "content": f"<<< Sentence >>>\n{text}"})

        payload = {
            "model":       self.cfg["model"],
            "messages":    messages,
            "temperature": self.cfg["temperature"],
        }
        headers = {
            "Authorization": f"Bearer {self.cfg['api_key']}",
            "Content-Type":  "application/json",
        }
        url = self.cfg["base_url"].rstrip("/") + "/v1/chat/completions"

        for attempt in range(1, self.cfg.get("max_retry", 3) + 1):
            try:
                r = self._session.post(url, headers=headers, json=payload,
                                       timeout=self.cfg.get("timeout", 30))
                r.raise_for_status()
                resp = r.json()
                text_out = resp["choices"][0]["message"]["content"].strip()
                usage    = resp.get("usage", {})
                return text_out, usage
            except Exception:
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
        DEEPL_PROVIDER: {
            "class":   "DeepLProvider",
            "api_key": "",          
            "max_retry": MAX_RETRY,
            "timeout":  15,
        },
        OPENAI_FORMAT_PROVIDER: {
            "class": "OpenAIFormatProvider",
            "base_url": OEPANI_FORMAT_BASE_URL,
            "api_key":  OEPANI_FORMAT_API_KEY,
            "model":    OPENAI_FORMAT_MODEL,
            "temperature":OPENAI_DEFAULT_TEMPERATURE,
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
                    ui.Label({"ID":"ProviderLabel","Text":"服务商","Weight":0.1}),
                    ui.ComboBox({"ID":"ProviderCombo","Weight":0.1}),
                    ui.Label({"ID":"TargetLangLabel","Text":"目标语言","Weight":0.1}),
                    ui.ComboBox({"ID":"TargetLangCombo","Weight":0.1}),
                    ui.Button({"ID":"TransButtonTab1","Text":"翻译","Weight":0.15}),
                    ui.Label({"ID": "StatusLabel", "Text": " ", "Alignment": {"AlignHCenter": True, "AlignVCenter": True},"Weight":0.1}),
                    #ui.TextEdit({"ID":"SubTxt","Text":"","ReadOnly":False,"Weight":0.8}),
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
                ]),
                ui.VGroup({"Weight":1},[
                    ui.TextEdit({"ID": "OriginalTxt", "Text": "","PlaceholderText": "", "Weight": 0.9, "Font": ui.Font({"PixelSize": 15}),"HTML" : False, }),
                    ui.Button({"ID": "TransButtonTab2", "Text": "", "Weight": 0.1}),
                    ui.TextEdit({"ID": "TranslateTxt", "Text": "","PlaceholderText": "", "Weight": 0.9, "Font": ui.Font({"PixelSize": 15}),"TextBackgroundColor": { "R": 0.2, "G": 0.2, "B": 0.2 }}),
                    

                ]),
                                 
                # ===== 4.2 配置页 =====
                ui.VGroup({"Weight":1},[
                    ui.HGroup({"Weight": 0.1}, [
                        ui.Label({"ID":"MicrosoftConfigLabel","Text": "Microsoft", "Alignment": {"AlignLeft": True}, "Weight": 0.1}),
                        ui.Button({"ID": "ShowAzure", "Text": "配置","Weight": 0.1,}),
                    ]),
                    ui.HGroup({"Weight":0.1}, [
                        ui.Label({"ID":"DeepLConfigLabel","Text":"DeepL","Weight":0.1}),
                        ui.Button({"ID":"ShowDeepL","Text":"配置","Weight":0.1}),
                    ]),
                    ui.HGroup({"Weight":0.1},[
                        ui.Label({"ID":"OpenAIFormatConfigLabel","Text":"OpenAI Format","Weight":0.1}),
                        ui.Button({"ID":"ShowOpenAIFormat","Text":"配置","Weight":0.1}),
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
openai_format_config_window = dispatcher.AddWindow(
    {
        "ID": "AITranslatorConfigWin",
        "WindowTitle": "AI Translator API",
        "Geometry": [750, 400, 350, 300],
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
                ui.Label({"ID": "OpenAIFormatLabel","Text": "填写AI Translator 信息", "Alignment": {"AlignHCenter": True, "AlignVCenter": True},"Weight": 0.1}),
                ui.Label({"ID":"OpenAIFormatModelLabel","Text":"模型","Weight":0.1}),
                ui.HGroup({"Weight": 0.2}, [
                    ui.ComboBox({"ID":"OpenAIFormatModelCombo","Weight":0.2}),  
                    ui.LineEdit({"ID": "OpenAIFormatModelName", "ReadOnly":True, "Text": ""}),
                ]),
                ui.Label({"ID": "OpenAIFormatBaseURLLabel", "Text": "* Base URL"}),
                ui.LineEdit({"ID": "OpenAIFormatBaseURL",  "Text": "","PlaceholderText":OEPANI_FORMAT_BASE_URL}),
                ui.Label({"ID": "OpenAIFormatApiKeyLabel", "Text": "* API Key"}),
                ui.LineEdit({"ID": "OpenAIFormatApiKey", "Text": "",  "EchoMode": "Password"}),
                ui.HGroup({"Weight": 0.2}, [
                    ui.Label({"ID": "OpenAIFormatTemperatureLabel", "Text": "* Temperature"}),
                ui.DoubleSpinBox({"ID": "OpenAIFormatTemperatureSpinBox", "Value": 0.3, "Minimum": 0.0, "Maximum": 1.0, "SingleStep": 0.01, "Weight": 1})
                ]),
                ui.HGroup({"Weight": 0.2}, [
                    ui.Button({"ID": "VerifyModel", "Text": "验证","Weight": 1}),
                    ui.Button({"ID": "ShowAddModel", "Text": "新增模型","Weight": 1}),
                    ui.Button({"ID": "DeleteModel", "Text": "删除模型","Weight": 1}),
                ]),
                ui.Label({"ID": "VerifyStatus", "Text": "", "Alignment": {"AlignHCenter": True}}),
                
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
deepL_config_window = dispatcher.AddWindow(
    {
        "ID": "DeepLConfigWin",
        "WindowTitle": "DeepL API",
        "Geometry": [780, 420, 350, 160],
        "Hidden": True,
        "StyleSheet": "*{font-size:14px;}"
    },
    [
        ui.VGroup([
            ui.Label({"ID":"DeepLLabel","Text":"DeepL API Key","Alignment":{"AlignHCenter":True}}),
            ui.HGroup({"Weight": 1}, [
                    ui.Label({"ID": "DeepLApiKeyLabel", "Text": "密钥", "Alignment": {"AlignRight": False}, "Weight": 0.2}),
                    ui.LineEdit({"ID":"DeepLApiKey","Text":"","EchoMode":"Password","Weight":0.8}),
                    
                ]),
            
            ui.HGroup([
                ui.Button({"ID":"DeepLConfirm","Text":"确定","Weight":1}),
                ui.Button({"ID":"DeepLRegister","Text":"注册","Weight":1}),
            ])
        ])
    ]
)
add_model_window = dispatcher.AddWindow(
    {
        "ID": "AddModelWin",
        "WindowTitle": "Add Model",
        "Geometry": [750, 400, 300, 200],
        "Hidden": True,
        "StyleSheet": "*{font-size:14px;}"
    },
    [
        ui.VGroup([
            ui.Label({"ID": "AddModelTitle", "Text": "添加 OpenAI 兼容模型", "Alignment": {"AlignHCenter": True, "AlignVCenter": True}}),
            ui.Label({"ID": "NewModelDisplayLabel", "Text": "Display name"}),
            ui.LineEdit({"ID": "addOpenAIFormatModelDisplay", "Text": ""}),
            ui.Label({"ID": "OpenAIFormatModelNameLabel", "Text": "* Model name"}),
            ui.LineEdit({"ID": "addOpenAIFormatModelName", "Text": ""}),
            ui.HGroup([
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

def show_dynamic_message(en_text, zh_text):
    """直接弹窗显示任意中英文文本的动态消息"""
    use_en = items["LangEnCheckBox"].Checked
    msg = en_text if use_en else zh_text
    msgbox.Show()
    msg_items["WarningLabel"].Text = msg

def on_msg_close(ev):
    msgbox.Hide()
msgbox.On.OkButton.Clicked = on_msg_close
msgbox.On.msg.Close = on_msg_close


translations = {
    "cn": {
        "Tabs": ["轨道翻译","单句翻译","配置"],
        "OpenAIFormatModelLabel":"选择模型：",
        "TargetLangLabel":"目标语音：",
        "TransButtonTab1":"开始翻译",
        "TransButtonTab2":"开始翻译",
        "OriginalTxt":"将文本粘贴到这里...",
        "TranslateTxt":"翻译",
        "MicrosoftConfigLabel":"Microsoft",
        "ShowAzure":"配置",
        "OpenAIFormatConfigLabel":"Open AI 格式",
        "ShowOpenAIFormat": "配置",
        "MoreScriptLabel":"\n———————更多功能———————",
        "TTSButton":"文字转语音（TTS）插件",
        "ProviderLabel":"服务商",
        "DeepLConfigLabel":"DeepL",
        "ShowDeepL":"配置",
        "DeepLLabel":"DeepL API",
        "DeepLApiKeyLabel":"密钥",
        "DeepLConfirm":"确定",
        "DeepLRegister":"注册",
        "AzureRegionLabel":"区域",
        "AzureApiKeyLabel":"密钥",
        "AzureConfirm":"确定",
        "AzureRegisterButton":"注册",
        "AzureLabel":"填写 Azure API 信息",
        "OpenAIFormatLabel":"填写 OpenAI Format API 信息",
        "VerifyModel":"验证",
        "ShowAddModel":"新增模型",
        "DeleteModel":"删除模型",
        "AddModelTitle":"添加 OpenAI 兼容模型",
        "OpenAIFormatModelNameLabel":"* 模型",
        "NewModelDisplayLabel":"显示名称",
        "AddModelBtn":"添加",
        
        
    },

    "en": {
        "Tabs": ["Translator","TextTrans", "Configuration"],
        "OpenAIFormatModelLabel":"Select Model:",
        "TargetLangLabel":"Target Language:",
        "TransButtonTab1":"Translate",
        "TransButtonTab2":"Translate",
        "OriginalTxt":"Paste the text here...",
        "TranslateTxt":"Translate",
        "MicrosoftConfigLabel":"Microsoft",
        "ShowAzure":"Config",
        "OpenAIFormatConfigLabel":"Open AI Format",
        "ShowOpenAIFormat": "Config",
        "MoreScriptLabel":"\n—————MORE FEATURES—————",
        "TTSButton":"Text to Speech (TTS) Script",
        "ProviderLabel":"Provider",
        "DeepLConfigLabel":"DeepL",
        "ShowDeepL":"Config",
        "DeepLLabel":"DeepL API",
        "DeepLApiKeyLabel":"Key",
        "DeepLConfirm":"OK",
        "DeepLRegister":"Sign-up",
        "AzureRegionLabel":"Region",
        "AzureApiKeyLabel":"Key",
        "AzureConfirm":"OK",
        "AzureRegisterButton":"Register",
        "AzureLabel":"Azure API",
        "OpenAIFormatLabel":"OpenAI Format API",
        "VerifyModel":"Verify",
        "ShowAddModel":"Add Model",
        "DeleteModel":"Delete Model",
        "AddModelTitle":"Add OpenAI Format Model",
        "OpenAIFormatModelNameLabel":"* Model name",
        "NewModelDisplayLabel":"Display name",
        "AddModelBtn":"Add",
        
        
    }
}    

items       = win.GetItems()
openai_items = openai_format_config_window.GetItems()
azure_items = azure_config_window.GetItems()
deepL_items = deepL_config_window.GetItems()
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
    "AZURE_DEFAULT_KEY":"",
    "AZURE_DEFAULT_REGION":"",
    "DEEPL_DEFAULT_KEY":"",
    "PROVIDER":0,
    "OEPANI_FORMAT_BASE_URL": "",
    "OEPANI_FORMAT_API_KEY": "",
    "OPENAI_FORMAT_MODEL": 0,
    "OEPANI_FORMAT_TEMPERATURE":0.3,
  
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
def update_openai_format_model_combo():
    openai_items["OpenAIFormatModelCombo"].Clear()
                # 预装官方模型
    for disp ,info in custom_models.get("models", {}).items():
        openai_items["OpenAIFormatModelCombo"].AddItem(disp)


    # 加载用户自定义
    for disp ,info in custom_models.get("custom_models", {}).items():
        openai_items["OpenAIFormatModelCombo"].AddItem(disp)

update_openai_format_model_combo()

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
            if item_id in ("TranslateTxt", "OriginalTxt"):
                items[item_id].Text = ""
                items[item_id].PlaceholderText = text_value 
        elif item_id in azure_items:    
            azure_items[item_id].Text = text_value
        elif item_id in openai_items:    
            openai_items[item_id].Text = text_value
        elif item_id in deepL_items:    
            deepL_items[item_id].Text = text_value
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
    
    items["TargetLangCombo"].CurrentIndex = saved_settings.get("TARGET_LANG", default_settings["TARGET_LANG"])
    items["LangCnCheckBox"].Checked = saved_settings.get("CN", default_settings["CN"])
    items["LangEnCheckBox"].Checked = saved_settings.get("EN", default_settings["EN"])
    items["ProviderCombo"].CurrentIndex = saved_settings.get("PROVIDER", default_settings["PROVIDER"])
    azure_items["AzureApiKey"].Text = saved_settings.get("AZURE_DEFAULT_KEY", default_settings["AZURE_DEFAULT_KEY"])
    azure_items["AzureRegion"].Text = saved_settings.get("AZURE_DEFAULT_REGION", default_settings["AZURE_DEFAULT_REGION"])
    deepL_items["DeepLApiKey"].Text = saved_settings.get("DEEPL_DEFAULT_KEY",default_settings["DEEPL_DEFAULT_KEY"])
    openai_items["OpenAIFormatModelCombo"].CurrentIndex = saved_settings.get("OPENAI_FORMAT_MODEL", default_settings["OPENAI_FORMAT_MODEL"])
    openai_items["OpenAIFormatBaseURL"].Text = saved_settings.get("OEPANI_FORMAT_BASE_URL", default_settings["OEPANI_FORMAT_BASE_URL"])
    openai_items["OpenAIFormatApiKey"].Text = saved_settings.get("OEPANI_FORMAT_API_KEY", default_settings["OEPANI_FORMAT_API_KEY"])
    openai_items["OpenAIFormatTemperatureSpinBox"].Value = saved_settings.get("OEPANI_FORMAT_TEMPERATURE", default_settings["OEPANI_FORMAT_TEMPERATURE"])
if items["LangEnCheckBox"].Checked :
    switch_language("en")
else:
    switch_language("cn")

def close_and_save(settings_file):
    settings = {

        "CN":items["LangCnCheckBox"].Checked,
        "EN":items["LangEnCheckBox"].Checked,
        "PROVIDER":items["ProviderCombo"].CurrentIndex,
        "AZURE_DEFAULT_KEY":azure_items["AzureApiKey"].Text,
        "AZURE_DEFAULT_REGION":azure_items["AzureRegion"].Text,
        "DEEPL_DEFAULT_KEY":deepL_items["DeepLApiKey"].Text,
        "OPENAI_FORMAT_MODEL": openai_items["OpenAIFormatModelCombo"].CurrentIndex,
        "OEPANI_FORMAT_BASE_URL": openai_items["OpenAIFormatBaseURL"].Text,
        "OEPANI_FORMAT_API_KEY": openai_items["OpenAIFormatApiKey"].Text,
        "OEPANI_FORMAT_TEMPERATURE": openai_items["OpenAIFormatTemperatureSpinBox"].Value,
        "TARGET_LANG":items["TargetLangCombo"].CurrentIndex,

    }

    save_settings(settings, settings_file)
# --- 4.4 Tab 切换 ---
def on_my_tabs_current_changed(ev):
    items["MyStack"].CurrentIndex = ev["Index"]
win.On.MyTabs.CurrentChanged = on_my_tabs_current_changed

# --- 4.5 打开 OpenAI 配置窗 ---
def on_show_openai_format(ev):
    openai_format_config_window.Show()
win.On.ShowOpenAIFormat.Clicked = on_show_openai_format

def on_openai_close(ev):
    print("OpenAI Format API setup is complete.")
    openai_format_config_window.Hide()
openai_format_config_window.On.AITranslatorConfigWin.Close = on_openai_close


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

def on_show_deepl(ev):
    deepL_config_window.Show()
win.On.ShowDeepL.Clicked = on_show_deepl

def on_deepl_close(ev):
    # 关闭窗口 & 写入 ProviderManager
    prov_manager.update_cfg(
        DEEPL_PROVIDER,
        api_key = deepL_items["DeepLApiKey"].Text.strip()
    )
    deepL_config_window.Hide()
deepL_config_window.On.DeepLConfirm.Clicked = on_deepl_close
deepL_config_window.On.DeepLConfigWin.Close = on_deepl_close

def on_deepl_register(ev):
    webbrowser.open("https://www.deepl.com/account/summary")   # 官网注册页
deepL_config_window.On.DeepLRegister.Clicked = on_deepl_register

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

    add_model_items["addOpenAIFormatModelDisplay"].Text = ""
    add_model_items["addOpenAIFormatModelName"].Text    = ""
    openai_format_config_window.Hide()
    add_model_window.Show()
openai_format_config_window.On.ShowAddModel.Clicked = on_show_add_model


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
        code = r.status_code            # 直接获取响应码
        r.raise_for_status()            # 如果不是 2xx，会抛出 HTTPError
        return True, "", code           # 成功时返回 True 和状态码
    except requests.exceptions.HTTPError as e:
        # HTTPError 中包含 .response，可以再提取状态码
        return False, str(e), e.response.status_code
    except Exception as e:
        # 其他网络错误（超时、连接失败等）
        # e.response 可能为 None
        code = getattr(e, 'response', None)
        code = code.status_code if code else None
        return False, str(e), code

def on_verify_model(ev):
    base_url = openai_items["OpenAIFormatBaseURL"].Text.strip() or OEPANI_FORMAT_BASE_URL
    model    = openai_items["OpenAIFormatModelName"].PlaceholderText.strip()
    api_key  = openai_items["OpenAIFormatApiKey"].Text.strip()
    ok,msg,code = verify_settings(base_url, api_key, model)
    if ok :
        show_warning_message(STATUS_MESSAGES.verify_success)
    else :
        code_map = {
            400: STATUS_MESSAGES.bad_request,
            401: STATUS_MESSAGES.unauthorized,
            403: STATUS_MESSAGES.forbidden,
            404: STATUS_MESSAGES.not_found,
            429: STATUS_MESSAGES.too_many_requests,
            500: STATUS_MESSAGES.internal_server_error,
            502: STATUS_MESSAGES.bad_gateway,
            503: STATUS_MESSAGES.service_unavailable,
            504: STATUS_MESSAGES.gateway_timeout,
        }
        # 用 dict.get 拿到对应消息，找不到就用 verify_code 兜底
        show_warning_message(code_map.get(code, STATUS_MESSAGES.verify_code))
        print(msg)
openai_format_config_window.On.VerifyModel.Clicked = on_verify_model

def on_delete_model(ev):
    display = openai_items["OpenAIFormatModelCombo"].CurrentText.strip()
    custom_tbl = custom_models.setdefault("custom_models", {})
    if display in custom_tbl:
        del custom_tbl[display]
        update_openai_format_model_combo()
    else:
        show_warning_message(STATUS_MESSAGES.model_deleted_failed)
    save_settings(custom_models, custom_models_file)
openai_format_config_window.On.DeleteModel.Clicked = on_delete_model

def on_add_model(ev):
    # === 0 读取输入 ===
    model   = add_model_items["addOpenAIFormatModelName"].Text.strip()
    display = add_model_items["addOpenAIFormatModelDisplay"].Text.strip() or model

    if not model:
        show_warning_message(STATUS_MESSAGES.parameter_error)
        return

    # === 1 只操作 custom_models["custom_models"] ===
    custom_tbl = custom_models.setdefault("custom_models", {})

    # === 2 查找重复 model ===
    for old_disp, info in list(custom_tbl.items()):
        if info.get("model") == model:
            # 找到相同 model → 更新 display 名
            if old_disp != display:
                # 先搬移到新 key
                custom_tbl[display] = info
                # 再删除旧 key
                del custom_tbl[old_disp]
                # 更新下拉框：先移除旧项，再添加新项
                update_openai_format_model_combo()
            # 已处理完毕，直接保存返回
            save_settings(custom_models, custom_models_file)

            openai_format_config_window.Show()
            add_model_window.Hide()
            return

    # === 3 未找到重复 model → 新增条目 ===
    custom_tbl[display] = {"model": model}
    openai_items["OpenAIFormatModelCombo"].AddItem(display)

    # === 4 持久化并关闭窗口 ===
    save_settings(custom_models, custom_models_file)
    openai_format_config_window.Show()
    add_model_window.Hide()

add_model_window.On.AddModelBtn.Clicked = on_add_model

def on_openai_model_changed(ev):
    """
    当 OpenAIFormatModelCombo 选中项发生变化时，
    实时更新 NewModelName、NewBaseURL、NewApiKey 的显示内容。
    """
    # 1. 获取下拉框当前显示名
    disp = openai_items["OpenAIFormatModelCombo"].CurrentText

    # 2. 从 custom_models 中查询：优先查“自定义”表，否则查“预装”表
    entry = (
        custom_models.get("custom_models", {}).get(disp)
        or custom_models.get("models", {}).get(disp)
    )

    # 3. 如果找到了 dict，就更新对应字段；否则清空或回退
    if isinstance(entry, dict):
        openai_items["OpenAIFormatModelName"].PlaceholderText = entry.get("model", "")
    else:
        # 无配置时可清空，也可回退到默认
        openai_items["OpenAIFormatModelName"].PlaceholderText = ""

# 4. 绑定事件：ComboBox 的 CurrentIndexChanged
openai_format_config_window.On.OpenAIFormatModelCombo.CurrentIndexChanged = on_openai_model_changed
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
    resolve, current_project, current_media_pool, current_root_folder, current_timeline, fps = connect_resolve()
    if not current_timeline:
        return False

    # 1. 禁用所有现有字幕轨
    states = {}
    for i in range(1, current_timeline.GetTrackCount("subtitle") + 1):
        states[i] = current_timeline.GetIsTrackEnabled("subtitle", i)
        if states[i]:
            current_timeline.SetTrackEnable("subtitle", i, False)

    # 2. 找第一条空轨，没有就新建
    target = next(
        (i for i in range(1, current_timeline.GetTrackCount("subtitle") + 1)
         if not current_timeline.GetItemListInTrack("subtitle", i)),
        None
    )
    if target is None:
        current_timeline.AddTrack("subtitle")
        target = current_timeline.GetTrackCount("subtitle")
    current_timeline.SetTrackEnable("subtitle", target, True)

    # —— 新增部分：在根目录下创建 / 获取 srt 子文件夹 —— #
    # 3. 检查是否已存在名为 "srt" 的子文件夹
    srt_folder = None
    for folder in current_root_folder.GetSubFolderList():
        if folder.GetName() == "srt":
            srt_folder = folder
            break
    # 4. 如果不存在，就创建一个
    if srt_folder is None:
        srt_folder = current_media_pool.AddSubFolder(current_root_folder, "srt")

    # 5. 切换到 srt 文件夹
    current_media_pool.SetCurrentFolder(srt_folder)

    # —— 导入并追加到轨道 —— #
    # 6. 导入 SRT 文件
    current_media_pool.ImportMedia([path])

    # 7. 从 srt_folder 中获取最新导入的剪辑
    clips = srt_folder.GetClipList()
    latest_clip = clips[-1]  # 列表最后一个即刚导入的

    # 8. 追加到时间线
    current_media_pool.AppendToTimeline([latest_clip])

    print("🎉 The subtitles were inserted into folder 'srt' and track #", target)
    return True


# =============== 并发翻译封装 ===============
def translate_parallel(texts, provider, target_code,
                       status_label=None, ctx_win=CONTEXT_WINDOW):
    total, done = len(texts), 0
    result = [None] * total
    total_tokens = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {}
        for idx, t in enumerate(texts):
            if isinstance(provider, OpenAIFormatProvider) and ctx_win > 0:
                pre = "\n".join(texts[max(0, idx-ctx_win):idx])
                suf = "\n".join(texts[idx+1: idx+1+ctx_win])
                fut = pool.submit(provider.translate, t, target_code, pre, suf)
            else:
                fut = pool.submit(provider.translate, t, target_code)
            futures[fut] = idx

        for f in concurrent.futures.as_completed(futures):
            i = futures[f]
            try:
                res = f.result()
                # 只有真正返回 tuple 才统计 token
                if isinstance(res, tuple):
                    text_i, usage = res
                    tokens = usage.get("total_tokens", 0)
                else:
                    text_i, tokens = res, 0
                result[i] = text_i
                total_tokens += tokens
            except Exception as e:
                result[i] = f"[失败: {e}]"
            done += 1

            if status_label:
                pct = int(done / total * 100)
                en = f"Start translating... {pct}% ({done}/{total})  Tokens used: {total_tokens}"
                zh = f"开始翻译... {pct}% （{done}/{total}）  已消耗令牌：{total_tokens}"
                show_dynamic_message(en, zh)
    return result,total_tokens


# =============== 主按钮逻辑（核心差异处 ★★★） ===============
def get_provider_and_target():
    """返回 (provider 实例, target_code)，出错时抛 {'en','zh'} 元组"""
    provider_name = items["ProviderCombo"].CurrentText
    target_name   = items["TargetLangCombo"].CurrentText
    print(provider_name)
    if provider_name == OPENAI_FORMAT_PROVIDER:
        if not (openai_items["OpenAIFormatBaseURL"].Text and openai_items["OpenAIFormatApiKey"].Text):
            show_warning_message(STATUS_MESSAGES.enter_api_key)
        
        model = openai_items["OpenAIFormatModelName"].PlaceholderText.strip()
        base_url   = openai_items["OpenAIFormatBaseURL"].Text.strip() or OEPANI_FORMAT_BASE_URL
        api_key    = openai_items["OpenAIFormatApiKey"].Text.strip()
        temperature = openai_items["OpenAIFormatTemperatureSpinBox"].Value
        # 更新 Provider 配置
        prov_manager.update_cfg(OPENAI_FORMAT_PROVIDER,
            model   = model,
            base_url= base_url,
            api_key = api_key,
            temperature = temperature
        )
        return prov_manager.get(OPENAI_FORMAT_PROVIDER), target_name

    if provider_name == AZURE_PROVIDER:
        #if not azure_items["AzureApiKey"].Text.strip():
        #    show_warning_message(STATUS_MESSAGES.enter_api_key)
        prov_manager.update_cfg(
            AZURE_PROVIDER,
            api_key = azure_items["AzureApiKey"].Text.strip(),
            region  = azure_items["AzureRegion"].Text.strip() or AZURE_DEFAULT_REGION
        )
        return prov_manager.get(AZURE_PROVIDER), AZURE_LANG_CODE_MAP[target_name]

    if provider_name == GOOGLE_PROVIDER:
        return prov_manager.get(GOOGLE_PROVIDER), GOOGLE_LANG_CODE_MAP[target_name]

    if provider_name == DEEPL_PROVIDER:
        if not deepL_items["DeepLApiKey"].Text.strip():
            show_warning_message(STATUS_MESSAGES.enter_api_key)
        prov_manager.update_cfg(
            DEEPL_PROVIDER,
            api_key = deepL_items["DeepLApiKey"].Text.strip()
        )
        return prov_manager.get(DEEPL_PROVIDER), GOOGLE_LANG_CODE_MAP[target_name]

    items["StatusLabel"].Text = "❌ 未识别的服务商"

def on_trans_clicked(ev):
    # ---------- 1 采集字幕 ----------
    resolve, proj, mpool, root, tl, fps = connect_resolve()
    subs = get_subtitles(tl)
    if not subs:
        show_warning_message(STATUS_MESSAGES.nosub)
        return

    # ---------- 2 Provider & 目标语种 ----------
    provider, target_code = get_provider_and_target()

    # ---------- 3 连通性轻量检测 ----------
    items["TransButtonTab1"].Enabled = False
    show_warning_message(STATUS_MESSAGES.initialize)
    try:
        # 只 ping 第一条，不保存结果，若异常说明 Key/额度等有问题
        provider.translate(subs[0]["text"], target_code)
    except requests.exceptions.HTTPError as e:
        # 拿到 HTTP 响应码
        code = e.response.status_code if e.response is not None else None
        # 状态码到 STATUS_MESSAGES 的映射
        code_map = {
            400: STATUS_MESSAGES.bad_request,
            401: STATUS_MESSAGES.unauthorized,
            403: STATUS_MESSAGES.forbidden,
            404: STATUS_MESSAGES.not_found,
            429: STATUS_MESSAGES.too_many_requests,
            500: STATUS_MESSAGES.internal_server_error,
            502: STATUS_MESSAGES.bad_gateway,
            503: STATUS_MESSAGES.service_unavailable,
            504: STATUS_MESSAGES.gateway_timeout,
        }
        # 显示对应的提示，找不到就用 initialize_fault
        show_warning_message(code_map.get(code, STATUS_MESSAGES.initialize_fault))
        print(f"初始化失败，HTTP状态码：{code}，异常：{e}")
        items["TransButtonTab1"].Enabled = True
        return
    except Exception as e:
        # 其它错误
        show_warning_message(STATUS_MESSAGES.initialize_fault)
        print(f"初始化失败，异常原因：{e}")
        items["TransButtonTab1"].Enabled = True
        return
    
    # ---------- 4 并发翻译 ----------
    show_dynamic_message(
        f"Start translating... 0% (0/{len(subs)})",
        f"开始翻译... 0% （0/{len(subs)}）"
    )
    texts = [s["text"] for s in subs]
    translated, total_tokens = translate_parallel(
        texts, provider, target_code, status_label=items["StatusLabel"]
    )
    for s, new_txt in zip(subs, translated):
        s["text"] = new_txt or ""

    # ---------- 5 写 SRT 并导入 ----------
    srt_dir  = os.path.join(script_path, "srt")
    srt_path = write_srt(
        subs,
        tl.GetStartFrame(),
        fps,
        tl.GetName(),
        target_code,
        output_dir=srt_dir
    )
    if import_srt_to_first_empty(srt_path):
        show_dynamic_message(
            f"✅ Finished! 100% ({len(subs)}/{len(subs)})  Tokens:{total_tokens}",
            f"✅ 翻译完成！100%（{len(subs)}/{len(subs)}）  Tokens:{total_tokens}"
        )
    else:
        items["StatusLabel"].Text = "⚠️ 导入失败！"

    items["TransButtonTab1"].Enabled = True
win.On.TransButtonTab1.Clicked = on_trans_clicked
# ---------------- 单句翻译按钮 ----------------
def on_trans2_clicked(ev):
    """
    翻译 OriginalTxt 单行文本 ➜ TranslateTxt
    """
    # ---------- 0 读取并检查源文本 ----------
    src = items["OriginalTxt"].PlainText
    # ---------- 1 Provider & 目标语言 ----------
    try:
        provider, target_code = get_provider_and_target()
    except Exception:
        return
    print(provider)
    items["TransButtonTab2"].Enabled = False
    # ---------- 2 轻量检测 & 翻译 ----------
    try:
        # 若 provider 是 OpenAIFormatProvider，translate 返回 (text, usage)
        if isinstance(provider, OpenAIFormatProvider):
            text_out, _ = provider.translate(src, target_code)
        else:
            res = provider.translate(src, target_code)
            # 有些 provider 返回 None，应特殊处理
            if not res or not isinstance(res, str):
                raise ValueError("翻译结果无效，未返回字符串")
            text_out = res
        show_warning_message(STATUS_MESSAGES.finished)
        items["TranslateTxt"].Text = text_out

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else None
        code_map = {
            400: STATUS_MESSAGES.bad_request,
            401: STATUS_MESSAGES.unauthorized,
            403: STATUS_MESSAGES.forbidden,
            404: STATUS_MESSAGES.not_found,
            429: STATUS_MESSAGES.too_many_requests,
            500: STATUS_MESSAGES.internal_server_error,
            502: STATUS_MESSAGES.bad_gateway,
            503: STATUS_MESSAGES.service_unavailable,
            504: STATUS_MESSAGES.gateway_timeout,
        }
        show_warning_message(code_map.get(code, STATUS_MESSAGES.initialize_fault))
        print(f"HTTPError {code}: {e}")

    except Exception as e:
        show_warning_message(STATUS_MESSAGES.initialize_fault)
        print("翻译失败:", e)
    items["TransButtonTab2"].Enabled = True
win.On.TransButtonTab2.Clicked = on_trans2_clicked
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
    openai_format_config_window.Show()
    add_model_window.Hide(); 
add_model_window.On.AddModelWin.Close = on_add_model_close
# =============== 9  运行 GUI ===============
win.Show(); 
dispatcher.RunLoop(); 
win.Hide(); 
openai_format_config_window.Hide()
azure_config_window.Hide()
msgbox.Hide()