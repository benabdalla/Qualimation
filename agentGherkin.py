import re
from typing import List

GHERKIN_STEP_MAP = {
    r"^Given I am on the (.+)$": lambda m: f'page.goto("{m.group(1)}")',
    r"^When I enter \"(.+)\" in the (.+) field$": lambda m: f'page.fill("#{m.group(2)}", "{m.group(1)}")',
    r"^Then I click the (.+) button$": lambda m: f'page.click("#{m.group(1)}")',
    r"^And I enter \"(.+)\" in the (.+) field$": lambda m: f'page.fill("#{m.group(2)}", "{m.group(1)}")',
    r"^And I click the (.+) button$": lambda m: f'page.click("#{m.group(1)}")'
}

def parse_gherkin_to_playwright(gherkin_scenario: str) -> str:
    lines = gherkin_scenario.strip().split("\n")
    code_lines: List[str] = [
        "from playwright.sync_api import sync_playwright",
        "",
        "with sync_playwright() as p:",
        "    browser = p.chromium.launch(headless=False)",
        "    page = browser.new_page()"
    ]

    for line in lines:
        line = line.strip()
        matched = False
        for pattern, handler in GHERKIN_STEP_MAP.items():
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                code_lines.append("    " + handler(match))
                matched = True
                break
        if not matched:
            code_lines.append(f"    # TODO: Unhandled step: {line}")

    code_lines.append("    browser.close()")
    return "\n".join(code_lines)


if __name__ == "__main__":
    gherkin = '''
    Given I am on the http://example.com/login
    When I enter "user" in the username field
    And I enter "pass" in the password field
    Then I click the login button
    '''

    playwright_code = parse_gherkin_to_playwright(gherkin)
    print(playwright_code)
