from playwright.async_api import Page


async def stealth_async(page: Page):
    """
    Aplica técnicas de evasão para mascarar o bot Playwright.
    Substitui a biblioteca 'playwright-stealth' que está desatualizada.
    """

    # 1. Remove a propriedade 'navigator.webdriver' (principal sinal de bot)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # 2. Emula plugins (Browsers headless geralmente não têm plugins)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5] 
        });
    """)

    # 3. Adiciona objeto 'window.chrome' (presente em navegadores Chrome reais)
    await page.add_init_script("""
        window.chrome = {
            runtime: {}
        };
    """)

    # 4. Mascara permissões padrão (Notification api)
    await page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
    """)

    # 5. WebGL Vendor Override (Esconde que é renderizado por software/headless)
    await page.add_init_script("""
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // 37445 = UNMASKED_VENDOR_WEBGL
            // 37446 = UNMASKED_RENDERER_WEBGL
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter(parameter);
        };
    """)
