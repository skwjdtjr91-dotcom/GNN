"""
NX Open Python - Feature Sequence Extractor
NX Part에서 명령어 시퀀스를 추출해서 RAG corpus용 JSON으로 저장
"""

import NXOpen
import NXOpen.Features
import NXOpen.UF
import json
import os
from datetime import datetime


def get_session():
    return NXOpen.Session.GetSession()


def get_feature_info(feature):
    """
    Feature 하나에서 정보 추출
    """
    info = {
        "name": feature.Name,
        "type": feature.FeatureType,
        "suppressed": feature.Suppressed,
        "parameters": {}
    }

    try:
        # Feature 파라미터 추출
        expressions = feature.GetExpressions()
        for exp in expressions:
            try:
                info["parameters"][exp.Name] = {
                    "value": exp.Value,
                    "type": str(exp.Type)
                }
            except:
                pass
    except:
        pass

    # Feature 타입별 상세 정보 추출
    feature_type = feature.FeatureType.upper()

    try:
        if "EXTRUDE" in feature_type or "EXTRUDED" in feature_type:
            info.update(get_extrude_info(feature))

        elif "FILLET" in feature_type or "EDGE_BLEND" in feature_type or "BLEND" in feature_type:
            info.update(get_fillet_info(feature))

        elif "CHAMFER" in feature_type:
            info.update(get_chamfer_info(feature))

        elif "SHELL" in feature_type:
            info.update(get_shell_info(feature))

        elif "REVOLVE" in feature_type:
            info.update(get_revolve_info(feature))

        elif "SKETCH" in feature_type:
            info.update(get_sketch_info(feature))

        elif "BOOLEAN" in feature_type or "UNITE" in feature_type or "SUBTRACT" in feature_type or "INTERSECT" in feature_type:
            info.update(get_boolean_info(feature))

    except Exception as e:
        info["detail_error"] = str(e)

    return info


def get_extrude_info(feature):
    """Extrude 상세 정보"""
    detail = {"detail": {}}
    try:
        extrude = feature
        # 파라미터에서 거리 추출
        exprs = feature.GetExpressions()
        for exp in exprs:
            name_lower = exp.Name.lower()
            if "distance" in name_lower or "depth" in name_lower or "limit" in name_lower:
                detail["detail"]["distance"] = exp.Value
            elif "draft" in name_lower:
                detail["detail"]["draft_angle"] = exp.Value
    except:
        pass
    return detail


def get_fillet_info(feature):
    """Fillet 상세 정보"""
    detail = {"detail": {}, "applied_edges": []}
    try:
        exprs = feature.GetExpressions()
        for exp in exprs:
            name_lower = exp.Name.lower()
            if "radius" in name_lower:
                detail["detail"]["radius"] = exp.Value

        # 적용된 face/edge 기하학 정보
        entities = feature.GetEntities()
        for entity in entities:
            try:
                edge_info = get_edge_geometry(entity)
                detail["applied_edges"].append(edge_info)
            except:
                pass
    except:
        pass
    return detail


def get_chamfer_info(feature):
    """Chamfer 상세 정보"""
    detail = {"detail": {}, "applied_edges": []}
    try:
        exprs = feature.GetExpressions()
        for exp in exprs:
            name_lower = exp.Name.lower()
            if "distance" in name_lower or "offset" in name_lower:
                detail["detail"]["distance"] = exp.Value

        entities = feature.GetEntities()
        for entity in entities:
            try:
                edge_info = get_edge_geometry(entity)
                detail["applied_edges"].append(edge_info)
            except:
                pass
    except:
        pass
    return detail


def get_shell_info(feature):
    """Shell 상세 정보"""
    detail = {"detail": {}, "open_faces": []}
    try:
        exprs = feature.GetExpressions()
        for exp in exprs:
            name_lower = exp.Name.lower()
            if "thickness" in name_lower:
                detail["detail"]["thickness"] = exp.Value

        entities = feature.GetEntities()
        for entity in entities:
            try:
                face_info = get_face_geometry(entity)
                detail["open_faces"].append(face_info)
            except:
                pass
    except:
        pass
    return detail


def get_revolve_info(feature):
    """Revolve 상세 정보"""
    detail = {"detail": {}}
    try:
        exprs = feature.GetExpressions()
        for exp in exprs:
            name_lower = exp.Name.lower()
            if "angle" in name_lower:
                detail["detail"]["angle"] = exp.Value
    except:
        pass
    return detail


def get_sketch_info(feature):
    """Sketch 상세 정보"""
    detail = {"detail": {}}
    try:
        sketch = NXOpen.Sketch(feature.Tag)
        detail["detail"]["sketch_name"] = sketch.Name

        # 스케치 평면 정보
        try:
            ref_plane = sketch.ReferenceDirection
            detail["detail"]["plane_normal"] = [
                round(ref_plane.X, 4),
                round(ref_plane.Y, 4),
                round(ref_plane.Z, 4)
            ]
        except:
            pass

    except:
        pass
    return detail


def get_boolean_info(feature):
    """Boolean 상세 정보"""
    detail = {"detail": {}}
    feature_type = feature.FeatureType.upper()
    if "UNITE" in feature_type:
        detail["detail"]["operation"] = "Unite"
    elif "SUBTRACT" in feature_type:
        detail["detail"]["operation"] = "Subtract"
    elif "INTERSECT" in feature_type:
        detail["detail"]["operation"] = "Intersect"
    return detail


def get_edge_geometry(entity):
    """Edge 기하학 정보"""
    edge_info = {"entity_type": "edge"}
    try:
        session = get_session()
        ufs = session.UFSession

        # Bounding box
        bbox = entity.GetBoundingBox()
        center = [
            round((bbox.MinXYZ.X + bbox.MaxXYZ.X) / 2, 4),
            round((bbox.MinXYZ.Y + bbox.MaxXYZ.Y) / 2, 4),
            round((bbox.MinXYZ.Z + bbox.MaxXYZ.Z) / 2, 4)
        ]
        edge_info["center"] = center
        edge_info["bbox_min"] = [
            round(bbox.MinXYZ.X, 4),
            round(bbox.MinXYZ.Y, 4),
            round(bbox.MinXYZ.Z, 4)
        ]
        edge_info["bbox_max"] = [
            round(bbox.MaxXYZ.X, 4),
            round(bbox.MaxXYZ.Y, 4),
            round(bbox.MaxXYZ.Z, 4)
        ]

        # Edge 타입 파악 (직선/원형 등)
        edge_info["z_position"] = round(center[2], 4)

    except Exception as e:
        edge_info["error"] = str(e)
    return edge_info


def get_face_geometry(entity):
    """Face 기하학 정보"""
    face_info = {"entity_type": "face"}
    try:
        bbox = entity.GetBoundingBox()
        center = [
            round((bbox.MinXYZ.X + bbox.MaxXYZ.X) / 2, 4),
            round((bbox.MinXYZ.Y + bbox.MaxXYZ.Y) / 2, 4),
            round((bbox.MinXYZ.Z + bbox.MaxXYZ.Z) / 2, 4)
        ]
        face_info["center"] = center
        face_info["z_position"] = round(center[2], 4)

    except Exception as e:
        face_info["error"] = str(e)
    return face_info


def extract_part_sequence(part):
    """
    Part 전체 Feature Sequence 추출
    메인 함수
    """
    result = {
        "part_name": part.Name,
        "file_path": part.FullPath,
        "extracted_at": datetime.now().isoformat(),
        "feature_count": 0,
        "sequence": []
    }

    order = 1
    for feature in part.Features:
        # 시스템 Feature 제외
        skip_types = ["DATUM_PLANE", "DATUM_AXIS", "DATUM_CSYS",
                      "COORDINATE_SYSTEM", "SKETCH_FEATURE_SET"]
        if any(skip in feature.FeatureType.upper() for skip in skip_types):
            continue

        # Suppressed Feature 제외 (선택사항 - 필요시 주석 해제)
        # if feature.Suppressed:
        #     continue

        feature_info = get_feature_info(feature)
        feature_info["order"] = order
        result["sequence"].append(feature_info)
        order += 1

    result["feature_count"] = len(result["sequence"])
    return result


def extract_to_json(output_dir=None):
    """
    현재 열린 Part에서 추출하고 JSON으로 저장
    """
    session = get_session()
    workPart = session.Parts.Work

    # Teamcenter 환경에서 Work Part가 None인 경우 Display Part 사용
    if workPart is None:
        workPart = session.Parts.Display

    if workPart is None:
        print("열린 Part가 없습니다.")
        return None

    print(f"추출 중: {workPart.Name}")

    # 추출 실행
    data = extract_part_sequence(workPart)

    # 저장 경로 (슬래시 정규화 - 한글/특수문자 경로 오류 방지)
    if output_dir is None:
        output_dir = os.path.dirname(workPart.FullPath)

    output_dir = output_dir.replace("\\", "/")
    os.makedirs(output_dir, exist_ok=True)

    # Part 이름 정제 (Teamcenter 파트번호에 / 포함될 수 있음)
    part_name = workPart.Name.replace(".prt", "")
    part_name = part_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    output_path = output_dir + "/" + part_name + "_sequence.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {output_path}")
    print(f"추출된 Feature 수: {data['feature_count']}")

    # 콘솔 출력
    print("\n=== Feature Sequence ===")
    for feat in data["sequence"]:
        params = feat.get("parameters", {})
        detail = feat.get("detail", {})
        print(f"[{feat['order']}] {feat['type']} | {feat['name']}")
        if detail:
            print(f"    상세: {detail}")
        if feat.get("applied_edges"):
            print(f"    적용 edge 수: {len(feat['applied_edges'])}")

    return output_path


def batch_extract(prt_dir, output_dir):
    """
    폴더 내 모든 .prt 파일 일괄 추출
    Teamcenter에서 체크아웃된 파일들 처리용
    """
    session = get_session()
    results = []

    prt_files = [f for f in os.listdir(prt_dir) if f.endswith(".prt")]
    print(f"발견된 .prt 파일: {len(prt_files)}개")

    for prt_file in prt_files:
        prt_path = os.path.join(prt_dir, prt_file)
        print(f"\n처리 중: {prt_file}")

        try:
            # Part 열기
            part, load_status = session.Parts.Open(prt_path)
            session.Parts.SetWork(part)

            # 추출
            output_path = extract_to_json(output_dir)
            results.append({
                "prt_file": prt_file,
                "output": output_path,
                "status": "success"
            })

            # Part 닫기
            session.Parts.CloseAll(
                NXOpen.BasePart.CloseWholeTree.FalseValue,
                None
            )

        except Exception as e:
            print(f"오류: {prt_file} - {str(e)}")
            results.append({
                "prt_file": prt_file,
                "status": "error",
                "error": str(e)
            })

    # 전체 결과 요약 저장
    summary_path = os.path.join(output_dir, "extraction_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n=== 배치 추출 완료 ===")
    print(f"성공: {sum(1 for r in results if r['status'] == 'success')}개")
    print(f"실패: {sum(1 for r in results if r['status'] == 'error')}개")

    return results


# ===== 실행 =====
if __name__ == "__main__":

    # 단일 Part 추출 (현재 열린 Part)
    extract_to_json(output_dir="D:/work/26 AI TF/01-2 설계 자동화")

    # 배치 추출 (폴더 전체)
    # batch_extract(
    #     prt_dir="C:/teamcenter_checkout",
    #     output_dir="D:/work/26 AI TF/01-2 설계 자동화"
    # )
