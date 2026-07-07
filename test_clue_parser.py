from game.clue_parser import parse_clue


def check(text, expected, label):
    result = parse_clue(text)
    status = "✅ OK" if result == expected else "❌ FAIL"
    print(f"{status}: {label!r} -> {result} (expected {expected})")
    if result != expected:
        raise SystemExit(1)


def main():
    check("2 طبیعت", (2, "طبیعت"), "حالت عادی با یه فاصله")
    check("2طبیعت", (2, "طبیعت"), "بدون هیچ فاصله‌ای")
    check("2  طبیعت", (2, "طبیعت"), "دو فاصله")
    check("2\u200cطبیعت", (2, "طبیعت"), "نیم‌فاصله (ZWNJ)")
    check("۲ طبیعت", (2, "طبیعت"), "عدد فارسی با فاصله")
    check("۲طبیعت", (2, "طبیعت"), "عدد فارسی بدون فاصله")
    check("٢ طبیعت", (2, "طبیعت"), "عدد عربی (Arabic-Indic)")
    check("  2   طبیعت  ", (2, "طبیعت"), "فاصله‌های اضافه دور کل پیام")
    check("12 آسمان", (12, "آسمان"), "عدد دو رقمی (برای اطمینان)")
    check("طبیعت 2", None, "ترتیب برعکس باید رد بشه")
    check("طبیعت", None, "بدون عدد باید رد بشه")
    check("2", None, "بدون کلمه باید رد بشه")
    check("", None, "متن خالی باید رد بشه")
    check(None, None, "None باید رد بشه")
    check("2\u200b طبیعت", (2, "طبیعت"), "zero-width space")
    check("2\u00a0طبیعت", (2, "طبیعت"), "non-breaking space")
    check("2/طبیعت", (2, "طبیعت"), "جداکننده‌ی اسلش")
    check("۲.طبیعت", (2, "طبیعت"), "جداکننده‌ی نقطه با عدد فارسی")
    check("2 انقلاب 57", (2, "انقلاب 57"), "کلمه‌ی سرنخ خودش شامل عدد باشه")
    check("2 1997", (2, "1997"), "کلمه‌ی سرنخ کاملاً عددی")

    print("\n🎉 همه‌ی تست‌های پارسر سرنخ رد شدن.")


if __name__ == "__main__":
    main()
