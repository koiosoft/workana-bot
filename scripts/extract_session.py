# extract_session.py
import asyncio
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page
from loguru import logger


def _build_anti_detection_script() -> str:
    """
    Build a comprehensive anti-detection JavaScript payload that overrides
    browser properties commonly checked by anti-bot systems (Workana, Cloudflare, etc.).

    Covers:
      - navigator.webdriver / plugins / languages / platform / hardwareConcurrency
      - window.chrome object simulation
      - WebGL vendor/renderer fingerprint spoofing (getParameter)
      - Canvas fingerprint noise injection (toDataURL / toBlob)
      - Permissions API override
      - Connection / battery / device-memory spoofing

    Returns:
        A minified JavaScript string ready for injection via page.add_init_script().
    """
    # ------------------------------------------------------------------
    # Core anti-detection logic — runs before any page JS executes
    # ------------------------------------------------------------------
    return """
// == Chrome Object Simulation ==
// Override navigator.webdriver (most common automation flag)
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// Override plugins array (headless Chrome often has 0 plugins)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
        ];
        plugins.item = (i) => plugins[i] || null;
        plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
        plugins.refresh = () => {};
        Object.setPrototypeOf(plugins, PluginArray.prototype);
        return plugins;
    }
});

// Spoof languages array
Object.defineProperty(navigator, 'languages', {
    get: () => ['es-ES', 'es', 'en-US', 'en']
});

// Spoof platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Linux x86_64'
});

// Override hardwareConcurrency (headless defaults to 1)
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// Spoof deviceMemory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// Simulate window.chrome (real Chrome exposes this object)
if (!window.chrome) {
    window.chrome = {
        runtime: {},
        loadTimes: () => {},
        csi: () => {},
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
        }
    };
}

// Spoof permissions API
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// -- WebGL Fingerprint Spoofing --
const getParameterProxyHandler = {
    apply: function(target, ctx, args) {
        const param = args[0];
        // UNMASKED_VENDOR_WEBGL
        if (param === 37445) return 'Google Inc. (Intel)';
        // UNMASKED_RENDERER_WEBGL
        if (param === 37446) return 'ANGLE (Intel, Mesa Intel(R) Graphics (ADL GT2), OpenGL 4.6)';
        return Reflect.apply(target, ctx, args);
    }
};

// Override WebGLRenderingContext.getParameter
const proxyWebGL = (originalGetParameter) => {
    return new Proxy(originalGetParameter, getParameterProxyHandler);
};

const hookWebGL = (contextProto) => {
    if (contextProto && contextProto.getParameter && !contextProto._antiDetectionHooked) {
        contextProto._antiDetectionHooked = true;
        const original = contextProto.getParameter;
        contextProto.getParameter = proxyWebGL(original);
    }
};

try { hookWebGL(WebGLRenderingContext.prototype); } catch(e) {}
try { hookWebGL(WebGL2RenderingContext.prototype); } catch(e) {}

// -- Canvas Fingerprint Noise Injection --
// Add subtle noise to canvas exports to prevent consistent fingerprinting
const injectCanvasNoise = (canvas) => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    // Add a semi-transparent noise pixel that won't be visually noticeable
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    if (imageData && imageData.data && imageData.data.length > 10) {
        const idx = (imageData.data.length - 4);
        imageData.data[idx] = imageData.data[idx] ^ 1;     // Flip LSB of red channel
        imageData.data[idx + 1] = imageData.data[idx + 1] ^ 1;
        ctx.putImageData(imageData, 0, 0);
    }
};

const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function() {
    if (arguments.length === 0 || arguments[0] === 'image/png') {
        try { injectCanvasNoise(this); } catch(e) {}
    }
    return originalToDataURL.apply(this, arguments);
};

const originalToBlob = HTMLCanvasElement.prototype.toBlob;
HTMLCanvasElement.prototype.toBlob = function(callback) {
    if (arguments.length === 0 || arguments[0] === 'image/png' || arguments[1] === 'image/png') {
        try { injectCanvasNoise(this); } catch(e) {}
    }
    return originalToBlob.apply(this, arguments);
};

// ================================================================
// CDP Marks & Automation Indicator Removal
// ================================================================

// -- Remove CDP runtime properties injected by Chromium DevTools --
// Chromium injects properties matching the pattern /^cdc_[a-zA-Z0-9]+$/.
// These are randomized per build but consistently detectable.
(function() {
    try {
        for (const key of Object.getOwnPropertyNames(window)) {
            if ((key.startsWith('cdc_') || key === 'webdriverPropertyValue')) {
                try { delete window[key]; } catch(_) {}
            }
        }
        // Also scan document for injected cdc_ properties
        for (const key of Object.getOwnPropertyNames(document)) {
            if (key.startsWith('cdc_')) {
                try { delete document[key]; } catch(_) {}
            }
        }
    } catch(_) {}
})();

// -- Remove known automation framework traces --
const automationTraces = [
    '__playwright', '__pw_manual', '__pw_init_scripts', '__PW_inspect',
    '__nightmare', 'callPhantom', '_phantom', '__phantomas',
    '__selenium_unwrapped', '__webdriver_evaluate', '__selenium_evaluate',
    '__webDriver', '__driver_evaluate', '__webdriver_script_fn',
    '__fxdriver_unwrapped', '__driver_unwrapped', '__webdriver_script_func',
    '__webdriver_script_function', '__lastWatirAlert', '__lastWatirConfirm',
    '__lastWatirPrompt', '_Selenium_IDE_Recorder', '_selenium', 'calledSelenium',
    '__WEBDRIVER_EVAL_FUNC_RESULT', 'Buffer', 'domAutomation', 'domAutomationController'
];
for (const prop of automationTraces) {
    try { delete window[prop]; } catch(_) {}
}

// -- Spoof navigator.productSub (some Chromium builds leak build date) --
Object.defineProperty(navigator, 'productSub', {
    get: () => '20030107'
});

// -- Spoof navigator.vendor to match real Chrome --
Object.defineProperty(navigator, 'vendor', {
    get: () => 'Google Inc.'
});

// -- Spoof MIME types array (headless Chrome often has 0 mimeTypes) --
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const mimeTypes = [
            { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
            { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }
        ];
        mimeTypes.item = (i) => mimeTypes[i] || null;
        mimeTypes.namedItem = (name) => mimeTypes.find(m => m.type === name) || null;
        Object.setPrototypeOf(mimeTypes, MimeTypeArray.prototype);
        return mimeTypes;
    }
});

// -- Override headless window/screen dimension detection --
// Headless Chrome defaults outerWidth/outerHeight to 0
if (window.outerWidth === 0 || window.outerHeight === 0) {
    Object.defineProperty(window, 'outerWidth', {
        get: () => screen.width || 1920
    });
    Object.defineProperty(window, 'outerHeight', {
        get: () => screen.height || 1080
    });
}

// -- Override Notification.permission (headless defaults to 'default') --
if (Notification.permission === 'default') {
    const originalNotification = window.Notification;
    Object.defineProperty(Notification, 'permission', {
        get: () => 'denied',
        configurable: true
    });
}

// -- Spoof navigator.mediaDevices to appear functional --
if (!navigator.mediaDevices) {
    Object.defineProperty(navigator, 'mediaDevices', {
        get: () => ({
            enumerateDevices: () => Promise.resolve([
                { deviceId: 'default', groupId: 'default', kind: 'audioinput', label: '' },
                { deviceId: 'default', groupId: 'default', kind: 'audiooutput', label: '' },
                { deviceId: 'default', groupId: 'default', kind: 'videoinput', label: '' }
            ]),
            getUserMedia: () => Promise.reject(new Error('NotAllowedError'))
        })
    });
}

// -- Override navigator.connection for non-Chrome / mobile detection evasion --
if (navigator.connection === undefined) {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false
        })
    });
}

// -- Patch matchMedia to avoid headless detection via resolution queries --
const originalMatchMedia = window.matchMedia;
window.matchMedia = function(query) {
    const result = originalMatchMedia.call(window, query);
    // Force matches to behave realistically for common resolution queries
    if (query.includes('prefers-color-scheme') && !result.matches) {
        return { matches: false, media: query, onchange: null,
                 addListener: () => {}, removeListener: () => {},
                 addEventListener: () => {}, removeEventListener: () => {},
                 dispatchEvent: () => false };
    }
    return result;
};
"""


def ensure_playwright_browsers():
    """Check if Chromium browser is installed; install it if missing."""
    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if not cache_dir.exists() or not list(cache_dir.glob("chromium-*")):
        logger.warning("⚠️ Navegadores Playwright no encontrados. Instalando Chromium...")
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            logger.success("✅ Chromium instalado correctamente.")
        except subprocess.CalledProcessError as e:
            logger.error(
                "❌ Falló la instalación de los navegadores Playwright:\n{}"
                .format(e.stdout.decode() if e.stdout else str(e))
            )
            raise


def _generate_human_delay(min_ms: int = 300, max_ms: int = 1500) -> float:
    """
    Generate a random delay (in seconds) to mimic human interaction timing.
    Uses a uniform distribution between min_ms and max_ms.
    """
    return random.randint(min_ms, max_ms) / 1000.0


async def _detect_challenge(page: Page) -> str | None:
    """
    Detect if the current page is presenting an anti-bot challenge.

    Returns:
        - 'cloudflare' if a Cloudflare JS challenge or Turnstile is detected.
        - 'hcaptcha'  if an hCaptcha widget is detected.
        - 'recaptcha' if a reCAPTCHA widget is detected.
        - None       if no challenge is present.
    """
    try:
        title = await page.title()
        content = await page.content()

        # Cloudflare "Checking your browser" interstitial
        cf_indicators = [
            "Just a moment...",
            "Checking your browser",
            "cf-browser-verification",
            "cf-challenge-running",
            "challenges.cloudflare.com",
            "cf-turnstile",
            "_cf_chl_opt",
        ]
        for indicator in cf_indicators:
            if indicator.lower() in title.lower() or indicator.lower() in content.lower():
                return "cloudflare"

        # hCaptcha detection
        hcaptcha_indicators = [
            "h-captcha",
            "hcaptcha.com",
            "data-hcaptcha-widget-id",
        ]
        for indicator in hcaptcha_indicators:
            if indicator.lower() in content.lower():
                return "hcaptcha"

        # reCAPTCHA detection
        recaptcha_indicators = [
            "recaptcha",
            "g-recaptcha",
            "google.com/recaptcha",
        ]
        for indicator in recaptcha_indicators:
            if indicator.lower() in content.lower():
                return "recaptcha"

    except Exception:
        pass

    return None


async def _handle_challenge(
    page: Page,
    max_wait_seconds: int = 120,
) -> bool:
    """
    Handle a detected anti-bot challenge page.

    ALL challenges require manual user resolution — no automatic solving.
    The script polls until the challenge disappears (user solved it) or timeout.

    Args:
        page:             The Playwright page with the challenge.
        max_wait_seconds: Maximum seconds to wait for manual resolution.

    Returns:
        True if the challenge was resolved by the user, False on timeout.
    """
    challenge_type = await _detect_challenge(page)
    if not challenge_type:
        return True  # No challenge to handle

    logger.warning(f"⚠️ Detectado desafío anti-bot: '{challenge_type}'")
    logger.warning(
        f"🛑 {challenge_type.upper()} — Debes resolverlo manualmente "
        f"en la ventana del navegador (timeout: {max_wait_seconds}s)."
    )

    elapsed = 0
    poll_interval = 2.0
    while elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        still_challenged = await _detect_challenge(page)
        if not still_challenged:
            logger.success("✅ Desafío resuelto manualmente.")
            await page.wait_for_timeout(int(_generate_human_delay(500, 1500) * 1000))
            return True
        if int(elapsed) % 10 == 0:
            logger.info(f"⏳ Esperando resolución manual... ({int(elapsed)}s/{max_wait_seconds}s)")

    logger.error(
        f"❌ Timeout esperando resolución manual del desafío ({max_wait_seconds}s)."
    )
    return False


async def capture_forced():
    ensure_playwright_browsers()

    browser_profile = {
        "user_agent": os.getenv(
            "WORKANA_USER_AGENT",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        ),
        "locale": os.getenv("WORKANA_LOCALE", "es-ES"),
        "timezone_id": os.getenv("WORKANA_TIMEZONE", "America/Santo_Domingo"),
        "extra_http_headers": {
            "Accept-Language": os.getenv("WORKANA_ACCEPT_LANGUAGE", "es-ES,es;q=0.9,en;q=0.8")
        },
        "viewport": {
            "width": int(os.getenv("WORKANA_VIEWPORT_WIDTH", "1920")),
            "height": int(os.getenv("WORKANA_VIEWPORT_HEIGHT", "1080")),
        },
    }

    # Build Chrome launch args from env, allowing runtime overrides
    disable_blink_features = os.getenv(
        "WORKANA_DISABLE_BLINK_FEATURES",
        "AutomationControlled",
    )
    chrome_args = [
        f"--disable-blink-features={disable_blink_features}",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-sandbox",
        "--disable-setuid-sandbox",
    ]
    # Allow injection of extra chrome args (comma-separated) for edge-case stealth tweaks
    extra_args_raw = os.getenv("WORKANA_EXTRA_CHROME_ARGS", "")
    if extra_args_raw:
        chrome_args.extend(
            arg.strip() for arg in extra_args_raw.split(",") if arg.strip()
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, # Necesitamos ver la pantalla para loguearnos
            args=chrome_args,
        )
        context = await browser.new_context(**browser_profile)
        # Inject anti-detection script before any page content loads
        await context.add_init_script(_build_anti_detection_script())
        page = await context.new_page()
        state_file = os.getenv("STATE_FILE_PATH", "app/state.json")

        # Ensure state_file path is writable as a regular file, not a directory.
        if os.path.exists(state_file) and not os.path.isfile(state_file):
            logger.warning(
                f"⚠️ {state_file} existe pero no es un archivo regular. "
                "Eliminando para evitar conflictos..."
            )
            try:
                if os.path.isdir(state_file):
                    shutil.rmtree(state_file)
                    logger.info(f"🗑️ Directorio {state_file} eliminado.")
                else:
                    os.remove(state_file)
                    logger.info(f"🗑️ Entrada inválida {state_file} eliminada.")
            except Exception as cleanup_err:
                logger.error(f"❌ No se pudo eliminar {state_file}: {cleanup_err}")
                return
        elif os.path.isfile(state_file):
            logger.info(f"📄 {state_file} ya existe. Será sobrescrito con la nueva sesión.")

        session_saved = False
        
        try:
            logger.info("🌐 Abriendo Workana para login manual...")
            # Add a small pre-navigation delay to mimic human behavior
            await asyncio.sleep(_generate_human_delay(200, 800))
            await page.goto("https://www.workana.com/login")

            # -- Cloudflare / anti-bot challenge detection and handling --
            challenge_detected = await _detect_challenge(page)
            if challenge_detected:
                resolved = await _handle_challenge(page)
                if not resolved:
                    logger.error(
                        "❌ No se pudo resolver el desafío anti-bot automáticamente. "
                        "Si ves un CAPTCHA en el navegador, resuélvelo manualmente."
                    )
                    # Don't abort — let the user handle it interactively

            logger.warning("👉 LOGUÉATE MANUALMENTE.")
            logger.info("Cuando veas tu dashboard, la sesión se guardará en state.json y el script terminará solo.")
            logger.info("Evita Ctrl+C para no interrumpir el guardado.")

            # Esperamos hasta que el usuario cierre el navegador.
            while True:
                await asyncio.sleep(1)
                if page.is_closed():
                    logger.warning("⚠️ Navegador cerrado antes de confirmar avatar; guardando estado final...")
                    break

                # Algunas navegaciones destruyen el contexto JS temporalmente.
                try:
                    avatar = await page.query_selector(".user-avatar")
                    user_menu = await page.query_selector(
                        ".dropdown-user-menu, [data-testid='user-menu'], .user-menu"
                    )
                    current_url = page.url or ""
                    is_login_url = "/login" in current_url
                    is_authenticated_url = any(
                        path in current_url
                        for path in ["/dashboard", "/projects", "/jobs", "/messages"]
                    )
                except Exception:
                    continue

                # Guardar solo cuando hay evidencia real de sesión autenticada.
                is_authenticated = bool(avatar or user_menu or (is_authenticated_url and not is_login_url))
                if is_authenticated and not session_saved:
                    await page.wait_for_timeout(1500)
                    await context.storage_state(path=state_file)
                    session_saved = True
                    logger.success("✅ Sesión detectada y guardada en state.json.")
                    break

        except asyncio.CancelledError:
            logger.warning("⚠️ Ejecución interrumpida antes de finalizar.")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            try:
                await context.storage_state(path=state_file)
                logger.info("💾 Estado final de sesión exportado a state.json.")
                session_saved = True
            except Exception as e:
                logger.warning(f"No se pudo exportar el estado final: {e}")

            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
            if session_saved:
                logger.info("📂 Archivo state.json listo para usar dentro de Docker.")
            else:
                logger.error("❌ No se pudo guardar state.json en esta ejecución.")

if __name__ == "__main__":
    try:
        asyncio.run(capture_forced())
    except KeyboardInterrupt:
        logger.warning("⛔ Proceso cancelado por teclado.")