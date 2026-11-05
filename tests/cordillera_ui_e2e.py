#!/usr/bin/env python3
"""Recorrido real desde el gateway. Ejecutar dentro de Kali."""
import re
import secrets

from playwright.sync_api import expect, sync_playwright


def main():
    base = "http://gateway:8080"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        expect(page.locator("#featured-products .product-card")).to_have_count(3)
        assert page.request.get(f"{base}/VulnerableApp/CommandInjection/LEVEL_1").status == 404
        catalog = page.request.get(f"{base}/api/catalog").json()
        assert (len(catalog["families"]), len(catalog["missions"])) == (20, 189)

        page.get_by_role("link", name="Empezar primer reto").click()
        expect(page.locator("#mission-detail")).to_contain_text("commandInjection-02")
        param = page.get_by_role("textbox", name="Valor de parámetro")
        expect(param).to_have_value("127.0.0.1")
        submit = page.get_by_role("button", name="Enviar y verificar")
        submit.click()
        expect(page.locator("#toast")).to_contain_text("Confirma")
        page.locator("#confirm-practice").check()
        submit.click()
        expect(page.locator("#lab-auth")).to_be_visible()
        page.get_by_label("Usuario del taller").fill("qa_store_" + secrets.token_hex(5))
        page.get_by_label("Contraseña del taller").fill(secrets.token_urlsafe(16))
        page.get_by_role("button", name="Crear cuenta").click()
        expect(page.locator("#lab-score")).to_contain_text("0 / 9800 XP")
        expect(page.locator("#lab-auth")).to_be_hidden()
        page.get_by_role("link", name="Volver al reto").click()

        result = page.locator("#response-panel")
        page.locator("#confirm-practice").check()
        submit.click()
        expect(result).to_contain_text("+0 XP", timeout=20000)
        assert "VA_LAB_OK" not in result.locator("pre").first.inner_text()
        page.get_by_role("button", name="Cargar ejemplo").click()
        expect(param).to_have_value("127.0.0.1|printf VA_LAB_OK")
        page.locator("#confirm-practice").check()
        submit.click()
        expect(result).to_contain_text("+100 XP", timeout=20000)
        expect(result.locator("pre").first).to_contain_text("VA_LAB_OK")
        assert result.locator("pre").first.inner_text().strip() == "VA_LAB_OK"
        page.locator("#confirm-practice").check()
        submit.click()
        expect(result).to_contain_text("+0 XP · Total 100 XP", timeout=20000)

        for width in (390, 768, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.locator("#lab-session-link").click()
        expect(page.locator("#lab-score")).to_contain_text("100 / 9800 XP")
        page.reload()
        expect(page.locator("#lab-score")).to_contain_text("100 / 9800 XP")
        page.get_by_role("button", name="Cerrar sesión").click()
        expect(page.locator("#lab-auth")).to_be_visible()

        page.goto(f"{base}/#mission=fileupload-01")
        expect(page.locator("#mission-detail")).to_contain_text("fileupload-01")
        expect(page.locator("#practice-form")).to_have_count(0)
        page.get_by_text("Pasos para practicar a mano en Kali", exact=True).click()
        expect(page.locator(".mission-steps")).to_contain_text("curl -i -X POST")

        page.goto(f"{base}/kali/vnc.html?autoconnect=1&resize=scale&path=websockify")
        expect(page.locator("html")).to_have_class(re.compile(r"\bnoVNC_connected\b"), timeout=25000)
        assert not errors, errors
        browser.close()
    print("PASS tienda, 189 retos, control, 100 XP, repetición, sesión, práctica guiada, móvil y noVNC")


if __name__ == "__main__":
    main()
