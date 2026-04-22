"""
NX Open Python - Feature Sequence Extractor
work_part.Sketches 방식으로 스케치 커브 정확히 추출
"""

import NXOpen
import NXOpen.Features
import json
import os
from datetime import datetime


def get_session():
    return NXOpen.Session.GetSession()


# ─── 헬퍼 ───────────────────────────────

def pt3(point):
    try:
        return [round(point.X, 4), round(point.Y, 4), round(point.Z, 4)]
    except:
        return []

def sf(value):
    try:
        return round(float(value), 4)
    except:
        return None

def feature_timestamp(feature):
    try:
        return feature.Timestamp
    except:
        return 999999

def normalize_type(feature):
    type_map = {
        "SWP104": "Sweep", "SWP105": "Sweep",
        "BLND": "Fillet", "CHMFR": "Chamfer",
        "BOSS": "Boss", "POCKET": "Pocket",
        "HOLE": "Hole", "THD": "Thread",
        "MIRR": "Mirror", "PTRN": "Pattern",
    }
    raw = getattr(feature, "FeatureType", "")
    return type_map.get(raw.upper(), raw)


# ─── 커브 추출 ───────────────────────────

def dump_curve(g):
    item = {"type": "curve"}
    # Line
    try:
        item["type"]  = "line"
        item["start"] = pt3(g.StartPoint)
        item["end"]   = pt3(g.EndPoint)
        return item
    except:
        pass
    # Arc / Circle
    try:
        item["center"] = pt3(g.CenterPoint)
        item["radius"] = sf(g.Radius)
        try:
            item["start"] = pt3(g.StartPoint)
            item["end"]   = pt3(g.EndPoint)
            item["type"]  = "arc"
        except:
            item["type"] = "circle"
        return item
    except:
        pass
    # 길이
    try:
        item["length"] = sf(g.GetLength())
    except:
        pass
    return item


# ─── 스케치 객체 덤프 ────────────────────

def dump_sketch_object(sk):
    data = {
        "name":       str(getattr(sk, "Name", "")),
        "journal_id": str(getattr(sk, "JournalIdentifier", "")),
        "plane":      "",
        "origin":     [],
        "normal":     [],
        "x_axis":     [],
        "datum_ref":  "",
        "entities":   [],
        "dimensions": []
    }

    # 스케치 원점
    try:
        data["origin"] = pt3(sk.Origin)
    except:
        pass

    # 스케치 X축 방향
    try:
        x = sk.ReferenceDirection
        data["x_axis"] = [round(x.X, 4), round(x.Y, 4), round(x.Z, 4)]
    except:
        pass

    # 법선 방향 (HelpPoint 기반)
    try:
        hp = sk.HelpPoint
        ox = data["origin"]
        if ox and hp:
            dx = hp.X - ox[0]
            dy = hp.Y - ox[1]
            dz = hp.Z - ox[2]
            length = (dx**2 + dy**2 + dz**2) ** 0.5
            if length > 0.001:
                data["normal"] = [round(dx/length, 4),
                                  round(dy/length, 4),
                                  round(dz/length, 4)]
    except:
        pass

    # 평면 이름 추론
    try:
        n = data["normal"]
        if n:
            if abs(n[2]) > 0.9:
                data["plane"] = "XY"
            elif abs(n[1]) > 0.9:
                data["plane"] = "XZ"
            elif abs(n[0]) > 0.9:
                data["plane"] = "YZ"
            else:
                data["plane"] = "custom"
    except:
        pass

    # 연결된 Datum CSYS 참조
    try:
        ref = sk.ReferenceCoordinateSystem
        if ref:
            data["datum_ref"] = str(getattr(ref, "Name", "")) or \
                                 str(getattr(ref, "JournalIdentifier", ""))
    except:
        pass

    # 커브
    try:
        for g in sk.GetAllGeometry():
            data["entities"].append(dump_curve(g))
    except:
        pass

    # 치수
    try:
        for d in sk.GetDimensions():
            dim = {"name": str(getattr(d, "Name", "")), "value": None}
            try:
                dim["value"] = sf(d.ComputedSize)
            except:
                pass
            data["dimensions"].append(dim)
    except:
        pass

    return data


# ─── Feature entities 추출 ───────────────

def get_feature_entities(feature):
    out = []
    try:
        for e in feature.GetEntities():
            item = {"class": str(type(e))}
            try:
                item["name"] = str(e.Name)
            except:
                pass
            try:
                item["journal_id"] = str(e.JournalIdentifier)
            except:
                pass
            try:
                item["point"] = pt3(e.Coordinates)
            except:
                pass
            out.append(item)
    except:
        pass
    return out


# ─── 시퀀스 빌드 ─────────────────────────

def build_sequence(work_part):
    # 1. Feature 목록 (타임스탬프 정렬)
    features = []
    for feat in work_part.Features:
        features.append(feat)
    features = sorted(features, key=lambda f: feature_timestamp(f))

    # 2. 실제 Sketch 객체 목록
    sketch_objects = []
    try:
        for sk in work_part.Sketches:
            sketch_objects.append(sk)
    except:
        pass

    # 3. Sketch feature 인덱스 수집
    sketch_feature_indices = []
    for i, feat in enumerate(features):
        if normalize_type(feat) == "SKETCH" or "SKETCH" in feat.FeatureType.upper():
            sketch_feature_indices.append(i)

    # 4. sketch feature ↔ sketch 객체 매핑
    sketch_map = {}
    for idx, feat_index in enumerate(sketch_feature_indices):
        if idx < len(sketch_objects):
            sketch_map[feat_index] = dump_sketch_object(sketch_objects[idx])

    # 5. 시퀀스 생성
    seq = []
    # Datum은 스킵하지 않고 참조 정보로 포함
    skip_types = []  # 아무것도 스킵 안 함 (Datum도 포함)
    datum_skip = ["DATUM_AXIS"]  # 축만 스킵

    for i, feat in enumerate(features, 1):
        raw_type = feat.FeatureType
        if any(s in raw_type.upper() for s in datum_skip):
            continue

        cmd = normalize_type(feat)
        feat_name = str(getattr(feat, "Name", ""))
        if not feat_name:
            feat_name = "{}({})".format(cmd, feat.Tag)

        item = {
            "step":         i,
            "command":      cmd,
            "name":         feat_name,
            "feature_type": raw_type,
            "journal_id":   str(getattr(feat, "JournalIdentifier", "")),
            "entities":     get_feature_entities(feat)
        }

        # Datum Plane
        if "DATUM_PLANE" in raw_type.upper():
            try:
                dp = NXOpen.DatumPlane(feat.Tag)
                item["command"] = "DatumPlane"
                item["detail"] = {
                    "origin": pt3(dp.Origin),
                    "normal": [round(dp.Normal.X, 4),
                               round(dp.Normal.Y, 4),
                               round(dp.Normal.Z, 4)]
                }
            except:
                item["command"] = "DatumPlane"

        # Datum CSYS
        elif "DATUM_CSYS" in raw_type.upper() or "COORDINATE_SYSTEM" in raw_type.upper():
            try:
                item["command"] = "DatumCSYS"
                params = {}
                for exp in feat.GetExpressions():
                    try:
                        params[exp.Name] = sf(exp.Value)
                    except:
                        pass
                item["detail"] = {"parameters": params}
            except:
                item["command"] = "DatumCSYS"

        # Sketch: sketch 객체 정보 추가
        elif "SKETCH" in raw_type.upper():
            sk_data = sketch_map.get(i - 1)
            if sk_data:
                item["sketch_name"]       = sk_data["name"]
                item["sketch_journal_id"] = sk_data["journal_id"]
                item["plane"]             = sk_data["plane"]
                item["origin"]            = sk_data["origin"]
                item["normal"]            = sk_data["normal"]
                item["x_axis"]            = sk_data["x_axis"]
                item["datum_ref"]         = sk_data["datum_ref"]
                item["entities"]          = sk_data["entities"]
                item["dimensions"]        = sk_data["dimensions"]
            else:
                item["dimensions"] = []

        # Extrude
        elif "EXTRUDE" in raw_type.upper() or "EXTRUDED" in raw_type.upper():
            item["detail"] = get_extrude_detail(feat)

        # Fillet
        elif any(k in raw_type.upper() for k in ["FILLET", "EDGE_BLEND", "BLEND", "BLND"]):
            item["detail"] = get_fillet_detail(feat)

        # Chamfer
        elif any(k in raw_type.upper() for k in ["CHAMFER", "CHMFR"]):
            item["detail"] = get_chamfer_detail(feat)

        # Shell
        elif "SHELL" in raw_type.upper():
            item["detail"] = get_shell_detail(feat)

        # Revolve
        elif "REVOLVE" in raw_type.upper():
            item["detail"] = get_revolve_detail(feat)

        else:
            params = {}
            try:
                for exp in feat.GetExpressions():
                    try:
                        params[exp.Name] = sf(exp.Value)
                    except:
                        pass
            except:
                pass
            item["detail"] = {"parameters": params}

        seq.append(item)

    return seq


# ─── Feature 상세 ────────────────────────

def get_extrude_detail(feature):
    detail = {
        "referenced_sketch": "",
        "distance_positive": None,
        "distance_negative": None,
        "boolean_type": "",
        "taper_angle": None
    }
    try:
        for exp in feature.GetExpressions():
            n = exp.Name.lower()
            v = exp.Value
            if "end" in n or "depth" in n or "distance" in n:
                if "start" in n or "negative" in n or "opposite" in n:
                    detail["distance_negative"] = sf(v)
                else:
                    detail["distance_positive"] = sf(v)
            elif "taper" in n or "draft" in n:
                detail["taper_angle"] = sf(v)
            elif "boolean" in n or "operation" in n:
                mapping = {0: "NewBody", 1: "Unite", 2: "Subtract", 3: "Intersect"}
                detail["boolean_type"] = mapping.get(int(v), str(v))
    except:
        pass
    try:
        for p in feature.GetParents():
            if "SKETCH" in p.FeatureType.upper():
                detail["referenced_sketch"] = p.Name
                break
    except:
        pass
    return detail


def get_edge_info(entity):
    info = {}
    try:
        bbox = entity.GetBoundingBox()
        info["center"] = [
            round((bbox.MinXYZ.X + bbox.MaxXYZ.X) / 2, 4),
            round((bbox.MinXYZ.Y + bbox.MaxXYZ.Y) / 2, 4),
            round((bbox.MinXYZ.Z + bbox.MaxXYZ.Z) / 2, 4)
        ]
        info["z_position"] = info["center"][2]
    except:
        pass
    return info


def get_face_info(entity):
    info = {}
    try:
        bbox = entity.GetBoundingBox()
        info["center"] = [
            round((bbox.MinXYZ.X + bbox.MaxXYZ.X) / 2, 4),
            round((bbox.MinXYZ.Y + bbox.MaxXYZ.Y) / 2, 4),
            round((bbox.MinXYZ.Z + bbox.MaxXYZ.Z) / 2, 4)
        ]
    except:
        pass
    return info


def get_fillet_detail(feature):
    detail = {"radius": None, "applied_edges": []}
    try:
        for exp in feature.GetExpressions():
            if "radius" in exp.Name.lower():
                detail["radius"] = sf(exp.Value)
                break
        for e in feature.GetEntities():
            try:
                detail["applied_edges"].append(get_edge_info(e))
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
                detail["distance"] = sf(exp.Value)
            elif "angle" in n:
                detail["angle"] = sf(exp.Value)
        for e in feature.GetEntities():
            try:
                detail["applied_edges"].append(get_edge_info(e))
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
                detail["thickness"] = sf(exp.Value)
                break
        for e in feature.GetEntities():
            try:
                detail["open_faces"].append(get_face_info(e))
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
                detail["angle"] = sf(exp.Value)
            elif "boolean" in n or "operation" in n:
                mapping = {0: "NewBody", 1: "Unite", 2: "Subtract", 3: "Intersect"}
                detail["boolean_type"] = mapping.get(int(exp.Value), str(exp.Value))
        for p in feature.GetParents():
            if "SKETCH" in p.FeatureType.upper():
                detail["referenced_sketch"] = p.Name
                break
    except:
        pass
    return detail


# ─── 저장 ────────────────────────────────

def extract_to_json(output_dir=None):
    session = get_session()
    workPart = session.Parts.Work

    if workPart is None:
        workPart = session.Parts.Display

    if workPart is None:
        print("열린 Part가 없습니다.")
        return None

    print("추출 중: {}".format(workPart.Name))

    sequence = build_sequence(workPart)

    result = {
        "part_name":    workPart.Name,
        "file_path":    workPart.FullPath,
        "extracted_at": datetime.now().isoformat(),
        "feature_count": len(sequence),
        "sequence":     sequence
    }

    if output_dir is None:
        output_dir = os.path.dirname(workPart.FullPath)

    output_dir = output_dir.replace("\\", "/")
    os.makedirs(output_dir, exist_ok=True)

    part_name = workPart.Name.replace(".prt", "")
    part_name = part_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    output_path = output_dir + "/" + part_name + "_sequence.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("저장 완료: {}".format(output_path))
    print("Feature 수: {}".format(len(sequence)))

    # 콘솔 요약
    print("\n=== Feature Sequence ===")
    for item in sequence:
        cmd = item["command"]
        print("[{}] {} | {}".format(item["step"], cmd, item["name"]))
        if cmd == "SKETCH":
            print("    커브 수: {}".format(len(item.get("entities", []))))
        elif "EXTRUDE" in cmd.upper():
            d = item.get("detail", {})
            print("    거리+: {} | 거리-: {} | Boolean: {}".format(
                d.get("distance_positive"),
                d.get("distance_negative"),
                d.get("boolean_type")))
        elif "FILLET" in cmd.upper() or "BLEND" in cmd.upper():
            d = item.get("detail", {})
            print("    반지름: {} | edge 수: {}".format(
                d.get("radius"), len(d.get("applied_edges", []))))
        elif "CHAMFER" in cmd.upper():
            d = item.get("detail", {})
            print("    거리: {} | edge 수: {}".format(
                d.get("distance"), len(d.get("applied_edges", []))))
        elif "SHELL" in cmd.upper():
            d = item.get("detail", {})
            print("    두께: {} | face 수: {}".format(
                d.get("thickness"), len(d.get("open_faces", []))))

    return output_path


# ─── 배치 추출 ───────────────────────────

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
    print("\n성공: {}개 / 실패: {}개".format(
        sum(1 for r in results if r["status"] == "success"),
        sum(1 for r in results if r["status"] == "error")))
    return results


# ─── 실행 ────────────────────────────────

if __name__ == "__main__":

    extract_to_json(output_dir="D:/work/26 AI TF/01-2 설계 자동화")

    # batch_extract(
    #     prt_dir="C:/teamcenter_checkout",
    #     output_dir="D:/work/26 AI TF/01-2 설계 자동화"
    # )
