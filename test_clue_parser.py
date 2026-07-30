from game.clue_parser import ParsedClue, parse_clue


def check(text, expected, label):
    result = parse_clue(text)
    status = "✅ OK" if result == expected else "❌ FAIL"
    print(f"{status}: {label!r} -> {result} (expected {expected})")
    if result != expected:
        raise SystemExit(1)


def main():
    check("2 طبیعت", ParsedClue(2, "طبیعت", 0), "حالت عادی با یه فاصله")
    check("2طبیعت", ParsedClue(2, "طبیعت", 0), "بدون هیچ فاصله‌ای")
    check("2  طبیعت", ParsedClue(2, "طبیعت", 0), "دو فاصله")
    check("2\u200cطبیعت", ParsedClue(2, "طبیعت", 0), "نیم‌فاصله (ZWNJ)")
    check("۲ طبیعت", ParsedClue(2, "طبیعت", 0), "عدد فارسی با فاصله")
    check("۲طبیعت", ParsedClue(2, "طبیعت", 0), "عدد فارسی بدون فاصله")
    check("٢ طبیعت", ParsedClue(2, "طبیعت", 0), "عدد عربی (Arabic-Indic)")
    check("  2   طبیعت  ", ParsedClue(2, "طبیعت", 0), "فاصله‌های اضافه دور کل پیام")
    check("12 آسمان", ParsedClue(12, "آسمان", 0), "عدد دو رقمی (برای اطمینان)")
    check("طبیعت 2", None, "ترتیب برعکس باید رد بشه")
    check("طبیعت", None, "بدون عدد باید رد بشه")
    check("2", None, "بدون کلمه باید رد بشه")
    check("", None, "متن خالی باید رد بشه")
    check(None, None, "None باید رد بشه")
    check("2\u200b طبیعت", ParsedClue(2, "طبیعت", 0), "zero-width space")
    check("2\u00a0طبیعت", ParsedClue(2, "طبیعت", 0), "non-breaking space")
    check("2/طبیعت", ParsedClue(2, "طبیعت", 0), "جداکننده‌ی اسلش")
    check("۲.طبیعت", ParsedClue(2, "طبیعت", 0), "جداکننده‌ی نقطه با عدد فارسی")
    check("2 انقلاب 57", ParsedClue(2, "انقلاب 57", 0), "کلمه‌ی سرنخ خودش شامل عدد باشه")
    check("2 1997", ParsedClue(2, "1997", 0), "کلمه‌ی سرنخ کاملاً عددی")

    # قانون ستاره
    check("3 دریا *", ParsedClue(3, "دریا", 1), "قانون ستاره - یک ستاره")
    check("4 دریا **", ParsedClue(4, "دریا", 2), "قانون ستاره - دو ستاره")
    check("4 دریا ⭐⭐", ParsedClue(4, "دریا", 2), "قانون ستاره - ایموجی ستاره")
    check("3 دریا*", ParsedClue(3, "دریا", 1), "قانون ستاره - بدون فاصله قبل از ستاره")

    print("\n🎉 همه‌ی تست‌های پارسر سرنخ رد شدن.")


if __name__ == "__main__":
    main()
