# -*- coding: utf-8 -*-
"""
범용 파일/폴더 네이밍 일괄 변경 도구
- 모드 1: 전/후 예시 입력 → 변환 규칙 자동 추론
- 모드 2: 찾을 문자열 + 바꿀 문자열 직접 입력
- 모드 3: 사이즈 매칭 → 기존 정상 네이밍을 따라가되 사이즈만 교체
- 대상: 폴더+파일 동시 / 파일만
- 미리보기 후 실제 변경, 실행 취소(undo) 지원

실행: python rename_tool.py  (또는 더블클릭)
필요: Python 3.8+ (표준 라이브러리만 사용, 추가 설치 불필요)
"""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# =====================================================
#  공통: 사이즈 패턴 (숫자x숫자)
# =====================================================
SIZE_RE = re.compile(r'(\d{2,5})[xX](\d{2,5})')


def extract_size(name):
    """파일명에서 '숫자x숫자' 사이즈를 추출. 없으면 None."""
    m = SIZE_RE.search(name)
    if m:
        return m.group(0)  # 예: "1080x1920"
    return None


def strip_size_and_ext(name):
    """사이즈와 확장자를 제거한 '소재 식별 본문' 반환 (그룹 묶기용 키)."""
    root, _ext = os.path.splitext(name)
    root = SIZE_RE.sub("", root)          # 사이즈 제거
    root = re.sub(r'[ _\-]+', '', root)    # 구분자 제거(느슨한 매칭)
    return root.lower()


# =====================================================
#  모드 1·2: 변환 규칙 추론 / 치환
# =====================================================
def infer_rule(before, after):
    before = before.strip()
    after = after.strip()
    if before == after:
        return None, None, "전/후 예시가 동일합니다."

    pre = 0
    while pre < len(before) and pre < len(after) and before[pre] == after[pre]:
        pre += 1
    suf = 0
    while (suf < len(before) - pre and suf < len(after) - pre
           and before[-1 - suf] == after[-1 - suf]):
        suf += 1

    before_mid = before[pre:len(before) - suf]
    after_mid = after[pre:len(after) - suf]

    if before_mid == "":
        rest = before[pre:]
        if rest == "":
            return "\x00APPEND", after_mid, None
        sep = "_-. "
        i = 0
        if rest[0] in sep:
            i = 1
        while i < len(rest) and rest[i] not in sep:
            i += 1
        anchor = rest[:i] if rest[:i] else rest[0]
        return anchor, after_mid + anchor, None

    return before_mid, after_mid, None


def apply_rule(name, find, replace, only_first=False):
    if find == "\x00APPEND":
        root, ext = os.path.splitext(name)
        return root + replace + ext
    if find == "":
        return name
    is_insert = find in replace
    if is_insert:
        inserted = replace.replace(find, "")
        if inserted and inserted in name:
            return name
        return name.replace(find, replace, 1)
    if only_first:
        return name.replace(find, replace, 1)
    return name.replace(find, replace)


# =====================================================
#  모드 3: 사이즈 매칭
#  같은 폴더 안에서 사이즈만 다른 파일끼리 묶고,
#  '기준 파일'(먼저 적재된 정상 네이밍)의 이름을 따라가되
#  사이즈 부분만 각 파일 자기 사이즈로 교체
# =====================================================
def make_size_matched_name(ref_name, target_name):
    """
    기준(ref) 파일명을 따라가되, 사이즈(숫자x숫자)만 target의 사이즈로 교체.
    확장자는 target 것을 유지.
    반환: (new_name, error_or_None)
    """
    ref_root, _ref_ext = os.path.splitext(ref_name)
    target_size = extract_size(target_name)
    if target_size is None:
        return None, "새 파일 이름에서 사이즈(숫자x숫자)를 찾을 수 없습니다."
    if extract_size(ref_root) is None:
        return None, "기준 파일 이름에 사이즈(숫자x숫자)가 없습니다."
    target_ext = os.path.splitext(target_name)[1]
    new_root = SIZE_RE.sub(target_size, ref_root)
    return new_root + target_ext, None


SQUARE_SIZE = "1080x1080"  # 정방향 기준 사이즈


def find_reference_file(files, square_size=SQUARE_SIZE):
    """
    files: [(path, name)]
    정방향(square_size) 사이즈를 포함하는 파일을 기준으로 반환.
    없으면 None.
    """
    for path, name in files:
        if square_size in name:
            return (path, name)
    return None


def auto_size_plan_for_folder(folder, files, square_size=SQUARE_SIZE):
    """
    한 폴더 안에서 정방향 파일을 기준으로 나머지 사이즈 파일들의 새 이름 계획 생성.
    반환: [(path, old_name, new_name, status, note)]
    """
    plan = []
    ref = find_reference_file(files, square_size)
    if ref is None:
        # 기준(정방향) 없음 → 전부 건너뜀
        for path, name in files:
            plan.append((path, name, name, "건너뜀", f"{square_size} 기준 파일 없음"))
        return plan

    ref_path, ref_name = ref
    for path, name in files:
        if path == ref_path:
            plan.append((path, name, name, "기준", "정방향 기준 (변경 안 함)"))
            continue
        if extract_size(name) is None:
            plan.append((path, name, name, "건너뜀", "사이즈 패턴 없음"))
            continue
        new_name, err = make_size_matched_name(ref_name, name)
        if err:
            plan.append((path, name, name, "건너뜀", err))
        elif new_name == name:
            plan.append((path, name, name, "건너뜀", "이미 동일"))
        else:
            plan.append((path, name, new_name, "예정", f"기준: {ref_name}"))
    return plan


def group_into_folders_plan(folder, files, square_size=SQUARE_SIZE):
    """
    같은 소재(사이즈·확장자 뺀 이름이 동일)끼리 묶어
    1080x1080 파일명(확장자 제외)으로 하위 폴더를 만들고 이동하는 계획 생성.

    files: [(path, name)]  (해당 folder 직속 파일들)
    반환: [(src_path, file_name, target_folder_name, status, note)]
    """
    # 사이즈·확장자 뺀 본문으로 그룹핑
    groups = {}
    for path, name in files:
        if extract_size(name) is None:
            # 사이즈 없는 파일은 그룹핑 대상에서 제외
            groups.setdefault("__NOSIZE__", []).append((path, name))
            continue
        key = strip_size_and_ext(name)
        groups.setdefault(key, []).append((path, name))

    plan = []
    for key, members in groups.items():
        if key == "__NOSIZE__":
            for path, name in members:
                plan.append((path, name, "", "건너뜀", "사이즈 패턴 없음"))
            continue

        # 폴더명 = 그룹 내 1080x1080 파일명(확장자 제외)
        ref = None
        for path, name in members:
            if square_size in name:
                ref = (path, name)
                break
        if ref is None:
            for path, name in members:
                plan.append((path, name, "", "건너뜀", f"{square_size} 파일 없음"))
            continue

        folder_name = os.path.splitext(ref[1])[0]  # 확장자 제거
        for path, name in members:
            plan.append((path, name, folder_name, "예정", f"폴더: {folder_name}"))
    return plan


# =====================================================
#  파일/폴더 수집
# =====================================================
def collect_items(root_dir, include_folders, recursive=True):
    items = []
    for cur, dirs, files in os.walk(root_dir):
        for f in files:
            items.append((os.path.join(cur, f), f, "파일"))
        if include_folders:
            for d in dirs:
                items.append((os.path.join(cur, d), d, "폴더"))
        if not recursive:
            break
    items.sort(key=lambda x: x[0].count(os.sep), reverse=True)
    return items


def collect_files_by_folder(root_dir, recursive=True):
    """폴더별로 파일 묶어서 반환: {folder: [(path, name)]}"""
    result = {}
    for cur, dirs, files in os.walk(root_dir):
        if files:
            result[cur] = [(os.path.join(cur, f), f) for f in files]
        if not recursive:
            break
    return result


# =====================================================
#  GUI
# =====================================================
class RenameApp:
    def __init__(self, root):
        self.root = root
        root.title("파일/폴더 네이밍 일괄 변경 도구")
        root.geometry("980x760")

        self.undo_stack = []

        # ── 1. 모드 선택 ──
        frame_mode = ttk.LabelFrame(root, text="① 작업 방식", padding=10)
        frame_mode.pack(fill="x", padx=12, pady=(12, 6))

        self.mode = tk.StringVar(value="example")
        ttk.Radiobutton(frame_mode, text="전/후 예시 입력 (자동 추론)",
                        variable=self.mode, value="example",
                        command=self._switch_mode).pack(side="left", padx=6)
        ttk.Radiobutton(frame_mode, text="찾기 / 바꾸기",
                        variable=self.mode, value="manual",
                        command=self._switch_mode).pack(side="left", padx=6)
        ttk.Radiobutton(frame_mode, text="사이즈 매칭 (기준 이름 따라가기)",
                        variable=self.mode, value="sizematch",
                        command=self._switch_mode).pack(side="left", padx=6)
        ttk.Radiobutton(frame_mode, text="폴더 그룹핑 (사이즈별 묶기)",
                        variable=self.mode, value="grouping",
                        command=self._switch_mode).pack(side="left", padx=6)

        # ── 2. 규칙 입력 영역 ──
        self.frame_rule = ttk.LabelFrame(root, text="② 규칙", padding=10)
        self.frame_rule.pack(fill="x", padx=12, pady=6)

        # 예시 모드
        self.lbl_b = ttk.Label(self.frame_rule, text="변경 전 예시:")
        self.entry_before = ttk.Entry(self.frame_rule, width=92)
        self.lbl_a = ttk.Label(self.frame_rule, text="변경 후 예시:")
        self.entry_after = ttk.Entry(self.frame_rule, width=92)

        # 수동 모드
        self.lbl_f = ttk.Label(self.frame_rule, text="찾을 문자열:")
        self.entry_find = ttk.Entry(self.frame_rule, width=92)
        self.lbl_r = ttk.Label(self.frame_rule, text="바꿀 문자열:")
        self.entry_replace = ttk.Entry(self.frame_rule, width=92)
        self.only_first = tk.BooleanVar(value=False)
        self.chk_first = ttk.Checkbutton(
            self.frame_rule, text="이름당 첫 번째 일치만 변경",
            variable=self.only_first)

        # 사이즈 매칭 모드 (자동 / 수동 서브선택)
        self.sm_sub = tk.StringVar(value="auto")
        self.fr_sm_sub = ttk.Frame(self.frame_rule)
        ttk.Radiobutton(self.fr_sm_sub, text="자동 (정방향 1080x1080 기준)",
                        variable=self.sm_sub, value="auto",
                        command=self._switch_mode).pack(side="left", padx=6)
        ttk.Radiobutton(self.fr_sm_sub, text="수동 (파일 1:1 선택)",
                        variable=self.sm_sub, value="manual",
                        command=self._switch_mode).pack(side="left", padx=6)

        # 자동용 안내
        self.sm_rename_folder = tk.BooleanVar(value=False)
        self.chk_sm_folder = ttk.Checkbutton(
            self.frame_rule,
            text="폴더명도 함께 변경 (폴더명이 기준 파일명과 다를 경우)",
            variable=self.sm_rename_folder)
        self.lbl_sm_auto = ttk.Label(
            self.frame_rule, foreground="#666",
            text="③ 대상 폴더를 선택하세요. 폴더 안에서 1080x1080 파일을 기준으로\n"
                 "나머지 사이즈 파일들을 기준 이름 + 자기 사이즈로 자동 변경합니다.\n"
                 "(하위 폴더 포함 시 여러 소재 폴더를 한 번에 처리)")

        # 수동(1:1)용 위젯
        self.sm_target = tk.StringVar()
        self.sm_ref = tk.StringVar()
        self.lbl_sm1 = ttk.Label(self.frame_rule, text="① 이름 바꿀 새 파일:")
        self.entry_sm_target = ttk.Entry(self.frame_rule, textvariable=self.sm_target, width=72)
        self.btn_sm_target = ttk.Button(self.frame_rule, text="파일 선택",
                                        command=self._choose_sm_target)
        self.lbl_sm2 = ttk.Label(self.frame_rule, text="② 기준 파일(따라갈 이름):")
        self.entry_sm_ref = ttk.Entry(self.frame_rule, textvariable=self.sm_ref, width=72)
        self.btn_sm_ref = ttk.Button(self.frame_rule, text="파일 선택",
                                     command=self._choose_sm_ref)
        self.lbl_sm_help = ttk.Label(
            self.frame_rule, foreground="#666",
            text="기준 파일 이름을 그대로 따라가되, 사이즈(숫자x숫자)만 새 파일 사이즈로 바꿉니다.")

        # 폴더 그룹핑 모드 안내
        self.lbl_gp_help = ttk.Label(
            self.frame_rule, foreground="#666",
            text="③ 대상 폴더를 선택하세요.\n"
                 "사이즈만 다른 같은 소재 파일들을 하나의 하위 폴더로 묶습니다.\n"
                 "새 폴더 이름 = 그룹의 1080x1080 파일명 (확장자 제외).\n\n"
                 "예) ..._1080x1080_JP.mp4 / ..._1080x1920_JP.mp4 / ..._1200x628_JP.mp4\n"
                 "  → [..._1080x1080_JP] 폴더 생성 후 3개 파일 이동")

        self._switch_mode()

        # ── 3. 대상 폴더 ──
        frame_dir = ttk.LabelFrame(root, text="③ 대상 폴더", padding=10)
        frame_dir.pack(fill="x", padx=12, pady=6)
        self.dir_var = tk.StringVar()
        ttk.Entry(frame_dir, textvariable=self.dir_var, width=82).pack(side="left", padx=(0, 8))
        ttk.Button(frame_dir, text="폴더 선택", command=self._choose_dir).pack(side="left")

        # ── 4. 옵션 ──
        self.frame_opt = ttk.LabelFrame(root, text="④ 변경 범위", padding=10)
        self.frame_opt.pack(fill="x", padx=12, pady=6)
        self.scope = tk.StringVar(value="files")
        self.rb_files = ttk.Radiobutton(self.frame_opt, text="파일명만 변경 (폴더명 유지)",
                        variable=self.scope, value="files")
        self.rb_all = ttk.Radiobutton(self.frame_opt, text="파일 + 폴더명 모두 변경",
                        variable=self.scope, value="all")
        self.rb_files.pack(side="left", padx=8)
        self.rb_all.pack(side="left", padx=8)
        self.recursive = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.frame_opt, text="하위 폴더까지 포함",
                        variable=self.recursive).pack(side="left", padx=20)

        # ── 5. 버튼 ──
        frame_btn = ttk.Frame(root)
        frame_btn.pack(fill="x", padx=12, pady=6)
        ttk.Button(frame_btn, text="🔍 미리보기", command=self.preview).pack(side="left", padx=4)
        ttk.Button(frame_btn, text="▶ 변경 실행", command=self.run).pack(side="left", padx=4)
        ttk.Button(frame_btn, text="↩ 실행 취소", command=self.undo).pack(side="left", padx=4)

        # ── 6. 결과 테이블 ──
        frame_tree = ttk.Frame(root)
        frame_tree.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        cols = ("종류", "변경 전", "변경 후", "상태")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (55, 350, 350, 110)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("change", background="#eafaf1")
        self.tree.tag_configure("skip", background="#fff9c4")
        self.tree.tag_configure("ref", background="#e3f2fd")
        self.tree.tag_configure("error", background="#fdedec")

        self.status = tk.StringVar(value="대기 중")
        ttk.Label(root, textvariable=self.status, anchor="w",
                  relief="sunken").pack(fill="x", side="bottom")

    # ---------------------------------------------
    def _hide_all_rule_widgets(self):
        for w in [self.lbl_b, self.entry_before, self.lbl_a, self.entry_after,
                  self.lbl_f, self.entry_find, self.lbl_r, self.entry_replace,
                  self.chk_first,
                  self.fr_sm_sub, self.lbl_sm_auto,
                  self.lbl_sm1, self.entry_sm_target, self.btn_sm_target,
                  self.lbl_sm2, self.entry_sm_ref, self.btn_sm_ref, self.lbl_sm_help,
                  self.chk_sm_folder, self.lbl_gp_help]:
            w.grid_forget()

    def _switch_mode(self):
        self._hide_all_rule_widgets()
        m = self.mode.get()
        if m == "example":
            self.lbl_b.grid(row=0, column=0, sticky="w", pady=3)
            self.entry_before.grid(row=0, column=1, sticky="w", pady=3)
            self.lbl_a.grid(row=1, column=0, sticky="w", pady=3)
            self.entry_after.grid(row=1, column=1, sticky="w", pady=3)
        elif m == "manual":
            self.lbl_f.grid(row=0, column=0, sticky="w", pady=3)
            self.entry_find.grid(row=0, column=1, sticky="w", pady=3)
            self.lbl_r.grid(row=1, column=0, sticky="w", pady=3)
            self.entry_replace.grid(row=1, column=1, sticky="w", pady=3)
            self.chk_first.grid(row=2, column=1, sticky="w", pady=3)
        else:  # sizematch
            self.fr_sm_sub.grid(row=0, column=0, columnspan=3, sticky="w", pady=3)
            if self.sm_sub.get() == "auto":
                self.chk_sm_folder.grid(row=1, column=0, columnspan=3, sticky="w", pady=3)
                self.lbl_sm_auto.grid(row=2, column=0, columnspan=3, sticky="w", pady=6)
            else:
                self.lbl_sm1.grid(row=1, column=0, sticky="w", pady=3)
                self.entry_sm_target.grid(row=1, column=1, sticky="w", pady=3)
                self.btn_sm_target.grid(row=1, column=2, sticky="w", padx=6)
                self.lbl_sm2.grid(row=2, column=0, sticky="w", pady=3)
                self.entry_sm_ref.grid(row=2, column=1, sticky="w", pady=3)
                self.btn_sm_ref.grid(row=2, column=2, sticky="w", padx=6)
                self.lbl_sm_help.grid(row=3, column=0, columnspan=3, sticky="w", pady=6)

        if m == "grouping":
            self.lbl_gp_help.grid(row=0, column=0, columnspan=3, sticky="w", pady=6)

        # 범위 옵션 제어
        if hasattr(self, "frame_opt"):
            if m in ("sizematch", "grouping"):
                self.scope.set("files")
                self.rb_files.config(state="disabled")
                self.rb_all.config(state="disabled")
            else:
                self.rb_files.config(state="normal")
                self.rb_all.config(state="normal")

    def _choose_dir(self):
        d = filedialog.askdirectory(title="대상 폴더 선택")
        if d:
            self.dir_var.set(d)

    def _choose_sm_target(self):
        f = filedialog.askopenfilename(title="이름 바꿀 새 파일 선택")
        if f:
            self.sm_target.set(f)
            if not self.dir_var.get():
                self.dir_var.set(os.path.dirname(f))

    def _choose_sm_ref(self):
        f = filedialog.askopenfilename(title="기준 파일 선택 (따라갈 이름)")
        if f:
            self.sm_ref.set(f)

    # ---------------------------------------------
    def _build_plan(self):
        """현재 설정 기준 변경 계획 리스트 생성.
        반환: [(path, old_name, new_name, kind, status, note)]"""
        m = self.mode.get()

        # 사이즈 매칭(1:1)은 폴더 대신 파일 2개를 직접 선택하므로 폴더 검증 생략
        if m != "sizematch":
            d = self.dir_var.get()
            if not d or not os.path.isdir(d):
                messagebox.showwarning("폴더 필요", "유효한 대상 폴더를 선택하세요.")
                return None

        # ── 사이즈 매칭 모드 ──
        if m == "sizematch":
            # 자동: 폴더 안 1080x1080 기준으로 일괄
            if self.sm_sub.get() == "auto":
                d = self.dir_var.get()
                if not d or not os.path.isdir(d):
                    messagebox.showwarning("폴더 필요", "대상 폴더를 선택하세요.")
                    return None
                by_folder = collect_files_by_folder(d, self.recursive.get())
                if not by_folder:
                    messagebox.showinfo("파일 없음", "선택한 폴더에 파일이 없습니다.")
                    return None
                rename_folder = self.sm_rename_folder.get()
                plan = []
                for folder, files in by_folder.items():
                    # 파일 사이즈 매칭 계획
                    sub = auto_size_plan_for_folder(folder, files)
                    for path, old, new, status, note in sub:
                        plan.append((path, old, new, "파일", status, note))

                    # 폴더명 변경 옵션 켜져 있으면 폴더명도 검토
                    if rename_folder:
                        ref = find_reference_file(files)
                        if ref:
                            ref_name = os.path.splitext(ref[1])[0]  # 확장자 제거
                            cur_folder_name = os.path.basename(folder)
                            if cur_folder_name != ref_name:
                                plan.append((
                                    folder,
                                    cur_folder_name,
                                    ref_name,
                                    "폴더",
                                    "예정",
                                    f"기준: {ref[1]}"
                                ))

                change_cnt = sum(1 for x in plan if x[4] == "예정")
                self.status.set(f"자동 사이즈 매칭: {len(plan)}개 중 {change_cnt}개 변경 예정")
                return plan
            # 수동 1:1
            else:
                target = self.sm_target.get().strip()
                ref = self.sm_ref.get().strip()
                if not target or not ref:
                    messagebox.showwarning("입력 필요", "새 파일과 기준 파일을 모두 선택하세요.")
                    return None
                if not os.path.isfile(target):
                    messagebox.showwarning("파일 없음", "새 파일 경로가 올바르지 않습니다.")
                    return None
                ref_name = os.path.basename(ref)
                target_name = os.path.basename(target)
                new_name, err = make_size_matched_name(ref_name, target_name)
                if err:
                    messagebox.showwarning("변환 불가", err)
                    return None
                status = "예정" if new_name != target_name else "건너뜀"
                note = f"기준: {ref_name}" if status == "예정" else "이미 동일"
                self.status.set("사이즈 매칭 준비 완료")
                return [(target, target_name, new_name, "파일", status, note)]

        # ── 폴더 그룹핑 모드 ──
        if m == "grouping":
            d = self.dir_var.get()
            if not d or not os.path.isdir(d):
                messagebox.showwarning("폴더 필요", "대상 폴더를 선택하세요.")
                return None
            # 그룹핑은 선택 폴더 직속 파일만 대상 (새로 만든 폴더 재순회 방지)
            by_folder = collect_files_by_folder(d, recursive=False)
            plan = []
            for folder, files in by_folder.items():
                sub = group_into_folders_plan(folder, files)
                for src_path, fname, target_folder, status, note in sub:
                    # new 칸에는 "이동할 폴더/파일명" 표기
                    if status == "예정":
                        disp = target_folder + "/" + fname
                    else:
                        disp = fname
                    # kind 칸에 folder 경로를 숨겨 전달 (실행 시 사용)
                    plan.append((src_path, fname, disp, "그룹이동", status, note))
            change_cnt = sum(1 for x in plan if x[4] == "예정")
            self.status.set(f"폴더 그룹핑: {len(plan)}개 중 {change_cnt}개 이동 예정")
            return plan

        # ── 예시 / 수동 모드 ──
        if m == "example":
            b, a = self.entry_before.get(), self.entry_after.get()
            if not b or not a:
                messagebox.showwarning("입력 필요", "변경 전/후 예시를 모두 입력하세요.")
                return None
            find, replace, err = infer_rule(b, a)
            if err:
                messagebox.showwarning("규칙 추론 실패", err)
                return None
            disp = "(확장자 앞 삽입)" if find == "\x00APPEND" else f'"{find}"'
            self.status.set(f'추론 규칙:  {disp}  →  "{replace}"')
            only_first = False
        else:
            find, replace = self.entry_find.get(), self.entry_replace.get()
            if not find:
                messagebox.showwarning("입력 필요", "찾을 문자열을 입력하세요.")
                return None
            only_first = self.only_first.get()

        include_folders = (self.scope.get() == "all")
        items = collect_items(d, include_folders, self.recursive.get())
        plan = []
        for path, name, kind in items:
            new_name = apply_rule(name, find, replace, only_first)
            status = "예정" if new_name != name else "건너뜀"
            note = "" if new_name != name else "변경 없음"
            plan.append((path, name, new_name, kind, status, note))
        return plan

    # ---------------------------------------------
    def _fill_tree(self, plan):
        self.tree.delete(*self.tree.get_children())
        for path, old, new, kind, status, note in plan:
            if status == "기준":
                tag = "ref"
            elif status in ("건너뜀",):
                tag = "skip"
            elif status == "오류":
                tag = "error"
            else:
                tag = "change"
            disp_new = new if new != old else (note or "(변경 없음)")
            self.tree.insert("", "end", values=(kind, old, disp_new, status), tags=(tag,))

    def preview(self):
        plan = self._build_plan()
        if plan is None:
            return
        self._fill_tree(plan)
        change_cnt = sum(1 for x in plan if x[4] == "예정")
        self.status.set(f"미리보기: 총 {len(plan)}개 중 {change_cnt}개 변경 예정")

    def run(self):
        plan = self._build_plan()
        if plan is None:
            return
        targets = [x for x in plan if x[4] == "예정"]
        if not targets:
            messagebox.showinfo("변경 없음", "변경할 항목이 없습니다.")
            self._fill_tree(plan)
            return
        if not messagebox.askyesno("확인",
                f"{len(targets)}개 항목의 이름을 변경합니다.\n계속하시겠습니까?"):
            return

        # 폴더는 파일 처리 끝난 뒤 (깊은 경로 먼저) 처리
        plan_sorted = sorted(
            plan,
            key=lambda x: (
                1 if x[3] == "폴더" else 0,          # 파일 먼저
                -x[0].count(os.sep)                   # 깊은 경로 먼저
            )
        )
        self.undo_stack.clear()
        ok = err = 0
        result = []
        for path, old, new, kind, status, note in plan_sorted:
            if status != "예정":
                result.append((path, old, new, kind, status, note))
                continue
            try:
                if kind == "그룹이동":
                    # note 에서 폴더명 추출: "폴더: <name>"
                    folder_name = note.replace("폴더: ", "").strip()
                    parent = os.path.dirname(path)
                    target_dir = os.path.join(parent, folder_name)
                    os.makedirs(target_dir, exist_ok=True)
                    new_path = os.path.join(target_dir, old)
                    if os.path.abspath(new_path) == os.path.abspath(path):
                        # 이미 제자리(기준 파일이 이미 그 폴더명과 같을 때)
                        result.append((path, old, new, kind, "건너뜀", "이미 위치함"))
                        continue
                    if os.path.exists(new_path):
                        raise FileExistsError("대상 폴더에 같은 파일 존재")
                    os.rename(path, new_path)
                    self.undo_stack.append((new_path, path))
                    result.append((new_path, old, new, kind, "완료", note))
                    ok += 1
                else:
                    if new == old:
                        result.append((path, old, new, kind, status, note))
                        continue
                    parent = os.path.dirname(path)
                    new_path = os.path.join(parent, new)
                    if os.path.exists(new_path):
                        raise FileExistsError("같은 이름 존재")
                    os.rename(path, new_path)
                    self.undo_stack.append((new_path, path))
                    result.append((new_path, old, new, kind, "완료", note))
                    ok += 1
            except Exception as e:
                result.append((path, old, new, kind, "오류", str(e)))
                err += 1
        self._fill_tree(result)
        self.status.set(f"완료: 변경 {ok} / 오류 {err}")
        messagebox.showinfo("완료", f"변경 {ok}개\n오류 {err}개")

    def undo(self):
        if not self.undo_stack:
            messagebox.showinfo("실행 취소", "되돌릴 항목이 없습니다.")
            return
        if not messagebox.askyesno("실행 취소",
                f"마지막 실행({len(self.undo_stack)}개)을 원복합니다.\n계속하시겠습니까?"):
            return
        cnt = 0
        for new_path, old_path in reversed(self.undo_stack):
            try:
                if os.path.exists(new_path):
                    os.rename(new_path, old_path)
                    cnt += 1
            except Exception:
                pass
        self.undo_stack.clear()
        self.status.set(f"원복 완료: {cnt}개")
        messagebox.showinfo("실행 취소", f"{cnt}개 원복 완료")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = RenameApp(root)
    root.mainloop()
