from ocrsnip.geometry import panel_rect

MON = (0, 0, 1920, 1080)
RIGHT_MON = (1920, 0, 1920, 1080)


def test_panel_is_quarter_screen_centered_on_pointer():
    x, y, w, h = panel_rect((960, 540), MON)
    assert (w, h) == (960, 540)          # 1/2 × 1/2 = 1/4 屏面积
    assert (x, y) == (480, 270)          # 以鼠标为中心
    assert x + w // 2 == 960 and y + h // 2 == 540


def test_panel_clamps_to_monitor_edges():
    left_top = panel_rect((0, 0), MON)
    assert left_top == (0, 0, 960, 540)

    right_bottom = panel_rect((1919, 1079), MON)
    assert right_bottom == (960, 540, 960, 540)


def test_panel_lands_on_the_monitor_under_the_pointer():
    x, y, w, h = panel_rect((2880, 540), RIGHT_MON)
    assert (x, y) == (2400, 270)
    assert x >= RIGHT_MON[0]  # 不会跨到左屏


def test_panel_respects_min_size_and_scale_bounds():
    tiny = panel_rect((100, 100), (0, 0, 600, 400), min_size=(360, 260))
    assert tiny[2:] == (360, 260)

    big = panel_rect((960, 540), MON, scale=2.0)   # 超范围会被夹回 1.0
    assert big[2:] == (1920, 1080)


def test_fullscreen_uses_whole_monitor():
    assert panel_rect((100, 100), MON, fullscreen=True) == MON


def test_explicit_size_wins_over_scale_and_min_size():
    # 300x200 比 min_size(360,260) 还小，但显式指定就该照做
    x, y, w, h = panel_rect((960, 540), MON, size=(300, 200))
    assert (w, h) == (300, 200)


def test_explicit_size_is_clamped_to_monitor():
    _x, _y, w, h = panel_rect((960, 540), MON, size=(99999, 99999))
    assert (w, h) == (MON[2], MON[3])


def test_one_dimension_explicit_other_follows_scale():
    _x, _y, w, h = panel_rect((960, 540), MON, scale=0.5, size=(800, 0))
    assert w == 800
    assert h == MON[3] // 2


def test_fullscreen_ignores_explicit_size():
    assert panel_rect((100, 100), MON, fullscreen=True, size=(300, 200)) == MON
