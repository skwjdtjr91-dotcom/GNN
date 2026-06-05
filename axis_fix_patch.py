# ============================================================
# 패치 1: derive_section_axis_from_view_and_cutline 함수 추가
# 위치: step_view_basis 함수 근처 (약 854라인 근처)에 추가
# ============================================================

def derive_section_axis_from_view_and_cutline(
    view_direction: str, cutline_axis: str
) -> str | None:
    """
    view 방향과 cutline 방향으로 실제 절단 축 결정.

    view_direction : "+X" | "-X" | "+Y" | "-Y" | "+Z" | "-Z"
    cutline_axis   : "vertical" | "horizontal"
    return         : "X" | "Y" | "Z" | None
    
    원리:
      - view=+Z/-Z (탑뷰):  세로선→Y절단, 가로선→X절단
      - view=+X/-X (프론트): 세로선→Z절단, 가로선→Y절단
      - view=+Y/-Y (사이드): 세로선→Z절단, 가로선→X절단
    """
    table: dict[tuple[str, str], str] = {
        ("+Z", "vertical"):   "Y",
        ("-Z", "vertical"):   "Y",
        ("+Z", "horizontal"): "X",
        ("-Z", "horizontal"): "X",
        ("+X", "vertical"):   "Z",
        ("-X", "vertical"):   "Z",
        ("+X", "horizontal"): "Y",
        ("-X", "horizontal"): "Y",
        ("+Y", "vertical"):   "Z",
        ("-Y", "vertical"):   "Z",
        ("+Y", "horizontal"): "X",
        ("-Y", "horizontal"): "X",
    }
    v = view_direction.upper().strip()
    c = cutline_axis.lower().strip()
    return table.get((v, c), None)


# ============================================================
# 패치 2: build_plan 함수 내 axis 결정 로직 수정
# 
# [변경 전] 약 1480~1492 라인:
# ============================================================
#
#     ocr_section_axis = section_axis_from_ocr_result(ocr_result)
#     axis = (args.section_axis or ocr_section_axis or cutline.get("marker_axis") or "X").upper()
#     if args.section_axis:
#         axis_source = "cli_override"
#     elif ocr_section_axis:
#         axis_source = "susun_sec_axis_ocr"
#     elif cutline.get("marker_axis"):
#         axis_source = "cutline_marker"
#     else:
#         axis_source = "default_x"
#     if axis not in {"X", "Y", "Z"}:
#         axis = "X"
#         axis_source = "invalid_axis_fallback_x"
#
# ============================================================
# [변경 후] axis 결정 블록을 step_view_match 이후(약 1497라인 이후)로 이동
# 아래 코드를 step_view_match = match_step_view_to_susun(...) 바로 다음에 배치
# ============================================================

    # ------------------------------------------------------------------
    # [이동됨] axis 결정: step_view_match 이후에 실행해야 view_dir 사용 가능
    # ------------------------------------------------------------------
    ocr_section_axis = section_axis_from_ocr_result(ocr_result)

    if args.section_axis:
        # 1순위: CLI override
        axis = args.section_axis.upper()
        axis_source = "cli_override"
    else:
        # 2순위: view 방향 + cutline 방향으로 기하학적 추론
        view_dir = (
            step_view_match.get("selected_view_direction", "")
            if step_view_match else ""
        )
        # cutline_axis: build_plan 1521라인에서 계산되는 "vertical"/"horizontal"
        # 단, cutline이 detected된 경우에만 사용 가능
        cutline_dir = ""
        if cutline.get("detected"):
            endpoints = cutline.get("endpoints_px", [])
            if len(endpoints) == 2:
                dy = abs(endpoints[1][1] - endpoints[0][1])
                dx = abs(endpoints[1][0] - endpoints[0][0])
                cutline_dir = "vertical" if dy >= dx else "horizontal"

        derived_axis = derive_section_axis_from_view_and_cutline(view_dir, cutline_dir)

        if derived_axis:
            axis = derived_axis
            axis_source = "view_cutline_derived"
        elif ocr_section_axis:
            # 3순위: OCR 텍스트에서 축 인식 (X-X, Y-Y 등)
            axis = ocr_section_axis
            axis_source = "susun_sec_axis_ocr"
        elif cutline.get("marker_axis"):
            # 4순위: cutline 마커 텍스트 (가장 신뢰도 낮음 - 텍스트만 보는 것)
            axis = cutline.get("marker_axis")
            axis_source = "cutline_marker"
        else:
            axis = "X"
            axis_source = "default_x"

    # axis 유효성 검사
    if axis not in {"X", "Y", "Z"}:
        axis = "X"
        axis_source = "invalid_axis_fallback_x"

    # ------------------------------------------------------------------
    # 기존 1490~1492 라인의 axis 결정 코드는 삭제
    # ------------------------------------------------------------------


# ============================================================
# 변경 요약
# ============================================================
# 1. derive_section_axis_from_view_and_cutline() 함수 신규 추가
#    - view_direction + cutline 방향(vertical/horizontal) → 절단축 결정
#
# 2. build_plan() 내 axis 결정 블록 이동 및 우선순위 변경
#    - 이동: 1480라인 → step_view_match 계산 이후(1497라인 뒤)
#    - 우선순위:
#      1) CLI override (args.section_axis)
#      2) view + cutline 기하학적 추론  ← 신규 (가장 신뢰도 높음)
#      3) OCR 텍스트 (X-X, Y-Y 등)
#      4) cutline marker_axis 텍스트
#      5) default "X"
#
# 3. axis_source에 "view_cutline_derived" 값 추가
#    - section_plan.json에서 추론 근거 확인 가능
#
# 핵심: "Section X-X'" 텍스트가 있어도 view+cutline 방향이
#       우선 적용되므로 Y방향 절단이 X로 잘못 잡히는 문제 해결
