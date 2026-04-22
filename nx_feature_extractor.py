"""
NX Open Python - Feature Sequence Extractor (상세 버전)
NX Part에서 명령어 시퀀스를 추출해서 RAG corpus용 JSON으로 저장

추출 정보:
- Sketch: 평면, 원점, 포함된 커브(Line/Arc/Circle) 좌표 및 파라미터
- Extrude: 참조 스케치, 방향, 거리(+/-), Boolean 타입
- Fillet: 반지름, 적용된 edge 위치/타입
- Chamfer: 거리, 적용된 edge 위치
- Shell: 두께, 열린 face 위치/법선
- Revolve: 참조 스케치, 회전 각도, Boolean 타입
"""

import NXOpen
import NXOpen.Features
import NXOpen.UF
import json
import os
from datetime import datetime


def get_session():
    return NXOpen.Session.GetSession()


# ─────────────────────────────────────────
# Sketch 상세 추출
# ─────────────────────────────────────────

def get_sketch_curves(sketch):
    """스케치 안의 커브(Line/Arc/Circle) 추출"""
    curves = []
    try:
        for curve in sketch.GetAllGeometry():
            curve_info = {}
            curve_type = type(curve).__name__

            if "Line" in curve_type:
                curve_info["type"] = "Line"
                try:
                    curve_info["start"] = [round(curve.StartPoint.X, 4),
                                           round(curve.StartPoint.Y, 4),
                                           round(curve.StartPoint.Z, 4)]
                    curve_info["end"]   = [round(curve.EndPoint.X, 4),
                                           round(curve.EndPoint.Y, 4),
                                           round(curve.EndPoint.Z, 4)]
                except:
                    pass

            elif "Arc" in curve_type:
                curve_info["type"] = "Arc"
                try:
                    curve_info["center"]      = [round(curve.CenterPoint.X, 4),
                                                 round(curve.CenterPoint.Y, 4),
                                                 round(curve.CenterPoint.Z, 4)]
                    curve_info["radius"]      = round(curve.Radius, 4)
                    curve_info["start_angle"] = round(curve.StartAngle, 4)
                    curve_info["end_angle"]   = round(curve.EndAngle, 4)
                except:
                    pass

            elif "Circle" in curve_type:
                curve_info["type"] = "Circle"
                try:
                    curve_info["center"] = [round(curve.CenterPoint.X, 4),
                                            round(curve.CenterPoint.Y, 4),
                                            round(curve.CenterPoint.Z, 4)]
                    curve_info["radius"] = round(curve.Radius, 4)
                except:
                    pass

            else:
                curve_info["type"] = curve_type

            if curve_info:
                curves.append(curve_info)
    except:
        pass
    return curves


def get_sketch_detail(feature):
    """Sketch Feature 상세 정보"""
    detail = {
        "plane": "",
        "origin": [],
        "normal": [],
        "curves": [],
        "curve_count": 0
    }
    try:
        sketch = NXOpen.Sketch(feature.Tag)

        try:
            origin = sketch.Origin
            detail["origin"] = [round(origin.X, 4),
                                 round(origin.Y, 4),
                                 round(origin.Z, 4)]
        except:
            pass

        try:
            normal = sketch.ReferenceDirection
            nx = round(normal.X, 4)
            ny = round(normal.Y, 4)
            nz = round(normal.Z, 4)
            detail["normal"] = [nx, ny, nz]

            if abs(nz) > 0.9:
                detail["plane"] = "XY"
            elif abs(ny) > 0.9:
                detail["plane"] = "XZ"
            elif abs(nx) > 0.9:
                detail["plane"] = "YZ"
            else:
                detail["plane"] = "custom({},{},{})".format(nx, ny, nz)
        except:
            pass

        curves = get_sketch_curves(sketch)
        detail["curves"] = curves
        detail["curve_count"] = len(curves)

    except:
        pass
    return detail


# ─────────────────────────────────────────
# Extrude 상세 추출
# ─────────────────────────────────────────

def get_extrude_detail(feature):
    """Extrude Feature 상세 정보"""
    detail = {
        "referenced_sketch": "",
        "distance_positive": None,
        "distance_negative": None,
        "boolean_type": "",
        "taper_angle": None
    }
    try:
        exprs = feature.GetExpressions()
        for exp in exprs:
            n = exp.Name.lower()
            v = exp.Value
            if "end" in n or "depth" in n or "distance" in n:
                if "start" in n or "negative" in n or "opposite" in n:
                    detail["distance_negative"] = round(v, 4)
                else:
                    detail["distance_positive"] = round(v, 4)
            elif "taper" in n or "draft" in n:
                detail["taper_angle"] = round(v, 4)
            elif "boolean" in n or "operation" in n:
                val = int(v)
                mapping = {0: "NewBody", 1: "Unite", 2: "Subtract", 3: "Intersect"}
                detail["boolean_type"] = mapping.get(val, str(val))
    except:
        pass

    try:
        parents = feature.GetParents()
        for p in parents:
            if "SKETCH" in p.FeatureType.upper():
                detail["referenced_sketch"] = p.Name
                break
    except:
        pass

    return detail


# ─────────────────────────────────────────
# Edge / Face 기하학 정보
# ─────────────────────────────────────────

def get_edge_detail(entity):
    """Edge 기하학 정보"""
    info = {}
    try:
        bbox = entity.GetBoundingBox()
        min_z = round(bbox.MinXYZ.Z, 4)
        max_z = round(bbox.MaxXYZ.Z, 4)
        cx = round((bbox.MinXYZ.X + bbox.MaxXYZ.X) / 2, 4)
        cy = round((bbox.MinXYZ.Y + bbox.MaxXYZ.Y) / 2, 4)
        cz = round((min_z + max_z) / 2, 4)

        info["center"] = [cx, cy, cz]
        info["bbox_min"] = [round(bbox.MinXYZ.X, 4), round(bbox.MinXYZ.Y, 4), min_z]
        info["bbox_max"] = [round(bbox.MaxXYZ.X, 4), round(bbox.MaxXYZ.Y, 4), max_z]
        info["z_position"] = cz

        dz = abs(max_z - min_z)
        dx = abs(bbox.MaxXYZ.X - bbox.MinXYZ.X)
        dy = abs(bbox.MaxXYZ.Y - bbox.MinXYZ.Y)

        if dz < 0.001:
            info["edge_orientation"] = "horizontal"
        else:
            info["edge_orientation"] = "vertical"

    except Exception as e:
        info["error"] = str(e)
    return info


def get_face_detail(entity):
    """Face 기하학 정보"""
    info = {}
    try:
        bbox = entity.GetBoundingBox()
        cx = round((bbox.MinXYZ.X + bbox.MaxXYZ.X) / 2, 4)
        cy = round((bbox.MinXYZ.Y + bbox.MaxXYZ.Y) / 2, 4)
        cz = round((bbox.MinXYZ.Z + bbox.MaxXYZ.Z) / 2, 4)

        info["center"] = [cx, cy, cz]
        info["z_position"] = cz
        info["size"] = [
            round(abs(bbox.MaxXYZ.X - bbox.MinXYZ.X), 4),
            round(abs(bbox.MaxXYZ.Y - bbox.MinXYZ.Y), 4),
            round(abs(bbox.MaxXYZ.Z - bbox.MinXYZ.Z), 4)
        ]
        dz = info["size"][2]
        info["face_orientation"] = "horizontal" if dz < 0.001 else "vertical"

    except Exception as e:
        info["error"] = str(e)
    return info


# ─────────────────────────────────────────
# Fillet / Chamfer / Shell / Revolve
# ─────────────────────────────────────────

def get_fillet_detail(feature):
    detail = {"radius": None, "applied_edges": []}
    try:
        for exp in feature.GetExpressions():
            if "radius" in exp.Name.lower():
                detail["radius"] = round(exp.Value, 4)
                break
        for entity in feature.GetEntities():
            try:
                detail["applied_edges"].append(get_edge_detail(entity))
            except:
                pass
    except:
        pass
    return detail


def get_chamfer_detail(feature):
    detail = {"distance": None, "angle": None, "applied_edges": []}
    try:
        for exp in feature.GetExpressions():
            n = exp.Name.lower()
            if "distance" in n or "offset" in n:
                detail["distance"] = round(exp.Value, 4)
            elif "angle" in n:
                detail["angle"] = round(exp.Value, 4)
        for entity in feature.GetEntities():
            try:
                detail["applied_edges"].append(get_edge_detail(entity))
            except:
                pass
    except:
        pass
    return detail


def get_shell_detail(feature):
    detail = {"thickness": None, "open_faces": []}
    try:
        for exp in feature.GetExpressions():
            if "thickness" in exp.Name.lower():
                detail["thickness"] = round(exp.Value, 4)
                break
        for entity in feature.GetEntities():
            try:
                detail["open_faces"].append(get_face_detail(entity))
            except:
                pass
    except:
        pass
    return detail


def get_revolve_detail(feature):
    detail = {"referenced_sketch": "", "angle": None, "boolean_type": ""}
    try:
        for exp in feature.GetExpressions():
            n = exp.Name.lower()
            if "angle" in n:
                detail["angle"] = round(exp.Value, 4)
            elif "boolean" in n or "operation" in n:
                val = int(exp.Value)
                mapping = {0: "NewBody", 1: "Unite", 2: "Subtract", 3: "Intersect"}
                detail["boolean_type"] = mapping.get(val, str(val))
        for p in feature.GetParents():
            if "SKETCH" in p.FeatureType.upper():
                detail["referenced_sketch"] = p.Name
                break
    except:
        pass
    return detail


# ─────────────────────────────────────────
# 메인 Feature 정보 추출
# ─────────────────────────────────────────

def get_feature_info(feature):
    """Feature 하나에서 전체 정보 추출"""
    info = {
        "name": feature.Name,
        "type": feature.FeatureType,
        "suppressed": feature.Suppressed,
        "detail": {}
    }

    ft = feature.FeatureType.upper()

    try:
        if "SKETCH" in ft:
            info["detail"] = get_sketch_detail(feature)
        elif "EXTRUDE" in ft or "EXTRUDED" in ft:
            info["detail"] = get_extrude_detail(feature)
        elif "FILLET" in ft or "EDGE_BLEND" in ft or "BLEND" in ft:
            info["detail"] = get_fillet_detail(feature)
        elif "CHAMFER" in ft:
            info["detail"] = get_chamfer_detail(feature)
        elif "SHELL" in ft:
            info["detail"] = get_shell_detail(feature)
        elif "REVOLVE" in ft:
            info["detail"] = get_revolve_detail(feature)
        else:
            params = {}
            try:
                for exp in feature.GetExpressions():
                    try:
                        params[exp.Name] = round(exp.Value, 4)
                    except:
                        pass
            except:
                pass
            info["detail"] = {"parameters": params}

    except Exception as e:
        info["detail"]["error"] = str(e)

    return info


# ─────────────────────────────────────────
# Part 전체 시퀀스 추출
# ─────────────────────────────────────────

def extract_part_sequence(part):
    result = {
        "part_name": part.Name,
        "file_path": part.FullPath,
        "extracted_at": datetime.now().isoformat(),
        "feature_count": 0,
        "sequence": []
    }

    skip_types = [
        "DATUM_PLANE", "DATUM_AXIS", "DATUM_CSYS",
        "COORDINATE_SYSTEM", "SKETCH_FEATURE_SET"
    ]

    order = 1
    for feature in part.Features:
        if any(skip in feature.FeatureType.upper() for skip in skip_types):
            continue
        feat_info = get_feature_info(feature)
        feat_info["order"] = order
        result["sequence"].append(feat_info)
        order += 1

    result["feature_count"] = len(result["sequence"])
    return result


# ─────────────────────────────────────────
# JSON 저장
# ─────────────────────────────────────────

def extract_to_json(output_dir=None):
    session = get_session()
    workPart = session.Parts.Work

    if workPart is None:
        workPart = session.Parts.Display

    if workPart is None:
        print("열린 Part가 없습니다.")
        return None

    print("추출 중: {}".format(workPart.Name))
    data = extract_part_sequence(workPart)

    if output_dir is None:
        output_dir = os.path.dirname(workPart.FullPath)

    output_dir = output_dir.replace("\\", "/")
    os.makedirs(output_dir, exist_ok=True)

    part_name = workPart.Name.replace(".prt", "")
    part_name = part_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    output_path = output_dir + "/" + part_name + "_sequence.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("저장 완료: {}".format(output_path))
    print("추출된 Feature 수: {}".format(data["feature_count"]))

    print("\n=== Feature Sequence ===")
    for feat in data["sequence"]:
        d = feat.get("detail", {})
        ft = feat["type"].upper()
        print("[{}] {} | {}".format(feat["order"], feat["type"], feat["name"]))
        if "SKETCH" in ft:
            print("    평면: {} | 커브 수: {}".format(
                d.get("plane"), d.get("curve_count")))
        elif "EXTRUDE" in ft:
            print("    스케치: {} | 거리+: {} | 거리-: {} | Boolean: {}".format(
                d.get("referenced_sketch"), d.get("distance_positive"),
                d.get("distance_negative"), d.get("boolean_type")))
        elif "BLEND" in ft or "FILLET" in ft:
            print("    반지름: {} | edge 수: {}".format(
                d.get("radius"), len(d.get("applied_edges", []))))
        elif "CHAMFER" in ft:
            print("    거리: {} | edge 수: {}".format(
                d.get("distance"), len(d.get("applied_edges", []))))
        elif "SHELL" in ft:
            print("    두께: {} | 열린 face 수: {}".format(
                d.get("thickness"), len(d.get("open_faces", []))))
        elif "REVOLVE" in ft:
            print("    스케치: {} | 각도: {} | Boolean: {}".format(
                d.get("referenced_sketch"), d.get("angle"), d.get("boolean_type")))

    return output_path


# ─────────────────────────────────────────
# 배치 추출
# ─────────────────────────────────────────

def batch_extract(prt_dir, output_dir):
    session = get_session()
    results = []

    prt_files = [f for f in os.listdir(prt_dir) if f.endswith(".prt")]
    print("발견된 .prt 파일: {}개".format(len(prt_files)))

    for prt_file in prt_files:
        prt_path = os.path.join(prt_dir, prt_file)
        print("\n처리 중: {}".format(prt_file))
        try:
            part, _ = session.Parts.Open(prt_path)
            session.Parts.SetWork(part)
            output_path = extract_to_json(output_dir)
            results.append({"prt_file": prt_file, "output": output_path, "status": "success"})
            session.Parts.CloseAll(NXOpen.BasePart.CloseWholeTree.FalseValue, None)
        except Exception as e:
            print("오류: {} - {}".format(prt_file, str(e)))
            results.append({"prt_file": prt_file, "status": "error", "error": str(e)})

    summary_path = output_dir.replace("\\", "/") + "/extraction_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n=== 배치 추출 완료 ===")
    print("성공: {}개".format(sum(1 for r in results if r["status"] == "success")))
    print("실패: {}개".format(sum(1 for r in results if r["status"] == "error")))
    return results


# ─────────────────────────────────────────
# 실행
# ─────────────────────────────────────────

if __name__ == "__main__":

    # 단일 Part 추출 (현재 열린 Part)
    extract_to_json(output_dir="D:/work/26 AI TF/01-2 설계 자동화")

    # 배치 추출 (폴더 전체)
    # batch_extract(
    #     prt_dir="C:/teamcenter_checkout",
    #     output_dir="D:/work/26 AI TF/01-2 설계 자동화"
    # )
