import time
import random
import pyautogui
import numpy as np
from PIL import ImageGrab
from paddleocr import PaddleOCR
from typing import List, Dict, Any, Tuple

# 1. OCR 初始化
# 确保 PaddleOCR 只初始化一次
ocr = PaddleOCR(use_textline_orientation=True, lang='ch')

# 2. 关键词
KEYWORD_PAYMENT = "立减"
KEYWORD_WALLET = "的小荷包"
KEYWORD_SUCCESS = "付款成功"
KEYWORD_CONFIRM = "确认还款"

# 3. 核心区域坐标
# 主监控区域
MONITOR_AREA = (1752, 841, 2533, 1402)
# 付款成功检测区域
PAYMENT_SUCCESS_AREA = (1742, 1060, 2485, 1377)
# 数字键盘区域
KEYPAD_AREA = (1768, 1131, 2529, 1388)
KEYPAD_LEFT, KEYPAD_TOP, KEYPAD_RIGHT, KEYPAD_BOTTOM = KEYPAD_AREA

# 4. 行为参数
CLICK_DURATION = 0.2  # 模拟点击的按下持续时间
PAYMENT_TIMEOUT = 10  # 付款成功检测超时时间（秒）
NUMBERS_TO_CLICK = [1, 5, 9, 6, 6, 7]  # 要点击的数字序列

# 5. 状态变量
# 拖动距离计数器
slide_distance_counter = 600  # 初始拖动距离为600像素

def local_ocr_paddle(left: int, top: int, right: int, bottom: int, keyword: str = "") -> List[Dict[str, Any]]:
    """
    在指定区域内识别文字。
    如果 keyword 为空，返回所有识别结果。
    否则，只返回包含 keyword 的结果。
    """
    img = ImageGrab.grab(bbox=(left, top, right, bottom))
    img_np = np.array(img)

    results = ocr.predict(img_np)
    if not results:
        return []

    candidates = []
    # PaddleOCR v4 返回的 results 结构是一个列表，其中每个元素是一个包含 'rec_texts', 'rec_scores', 'rec_boxes' 的字典
    for res in results:
        texts = res['rec_texts']
        scores = res['rec_scores']
        boxes = res['rec_boxes']

        for text, score, box in zip(texts, scores, boxes):
            # 如果keyword为空，返回所有结果；否则只返回包含关键词的结果
            if not keyword or keyword in text:
                # 'box' 是一个包含4个[x, y]坐标的列表
                box_np = np.array(box).reshape(-1, 2)
                x_min, y_min = box_np.min(axis=0)
                x_max, y_max = box_np.max(axis=0)
                cx = (x_min + x_max) / 2.0
                cy = (y_min + y_max) / 2.0
                candidates.append({
                    "cx": cx,  # 相对坐标
                    "cy": cy,  # 相对坐标
                    "text": text,
                    "score": score
                })
    return candidates

def check_payment_success() -> bool:
    """检测付款成功区域是否有'付款成功'文字"""
    left, top, right, bottom = PAYMENT_SUCCESS_AREA
    candidates = local_ocr_paddle(left, top, right, bottom, KEYWORD_SUCCESS)
    return len(candidates) > 0

def check_and_handle_payment_success(timeout: int = PAYMENT_TIMEOUT) -> bool:
    """
    在指定超时时间内检测付款成功，并执行返回操作。
    :return: 是否检测到付款成功
    """
    print(f"开始检测 {KEYWORD_SUCCESS}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if check_payment_success():
            print(f"检测到 '{KEYWORD_SUCCESS}'，执行ESC操作...")
            time.sleep(1.1)  # 等待动画或延迟
            pyautogui.press("esc")
            print("已触发返回事件 (ESC)")
            return True
        time.sleep(0.05)  # 短暂延迟避免过度占用CPU

    print(f"{timeout}秒内未检测到 {KEYWORD_SUCCESS}")
    return False


def click_sequence_numbers(numbers: List[int]):
    """
    先识别所有数字坐标，然后依次快速点击指定数字序列。
    """
    print("开始识别数字键盘区域，请等待2秒...")
    time.sleep(1)  # 等待1秒确保屏幕稳定

    # 一次性识别所有数字
    all_digits = local_ocr_paddle(KEYPAD_LEFT, KEYPAD_TOP, KEYPAD_RIGHT, KEYPAD_BOTTOM, "")

    # 过滤出数字并构建坐标映射
    digit_coordinates = {}
    for candidate in all_digits:
        text = candidate["text"].strip()
        if text.isdigit() and len(text) == 1:  # 只处理单个数字
            digit = int(text)
            # 转换为绝对屏幕坐标
            click_x = KEYPAD_LEFT + candidate["cx"]
            click_y = KEYPAD_TOP + candidate["cy"]

            if digit not in digit_coordinates:
                digit_coordinates[digit] = []

            digit_coordinates[digit].append({
                "x": click_x,
                "y": click_y,
                "score": candidate["score"]
            })
            print(f"识别到数字 {digit}: 坐标({click_x:.1f}, {click_y:.1f}), 置信度={candidate['score']:.2f}")

    # 检查是否找到了所有需要的数字
    required_digits = set(numbers)
    found_digits = set(digit_coordinates.keys())
    missing_digits = required_digits - found_digits

    if missing_digits:
        print(f"警告：未找到数字 {missing_digits}，无法继续点击序列。")
        return

    # 为每个数字位置选择最佳的坐标（按置信度排序）
    best_coordinates = {}
    used_positions = set()  # 用于记录已使用的坐标，避免重复点击同一个位置

    # 这个循环是为了处理数字在键盘上出现多次的情况（虽然不太可能，但是增加了鲁棒性）
    for num in numbers:
        candidates = digit_coordinates[num]
        candidates.sort(key=lambda c: c["score"], reverse=True)

        found = False
        for candidate in candidates:
            pos_key = (candidate["x"], candidate["y"])
            if pos_key not in used_positions:
                best_coordinates[num] = candidate
                used_positions.add(pos_key)
                found = True
                break

        # 如果所有位置都被用了（例如序列中有重复数字），就用置信度最高的那个
        if not found:
            best_coordinates[num] = candidates[0]

    print("开始快速点击数字序列...")

    # 快速点击所有数字
    for i, num in enumerate(numbers):
        coord = best_coordinates[num]
        print(f"点击数字 {num}: 坐标({coord['x']:.1f}, {coord['y']:.1f})")

        pyautogui.mouseDown(coord["x"], coord["y"])
        time.sleep(0.1)  # 缩短点击时间
        pyautogui.mouseUp(coord["x"], coord["y"])

        if i < len(numbers) - 1:
            time.sleep(0.2)  # 数字之间的短暂间隔

        # ✅ 数字 7 的特殊逻辑
        if num == 7:
            print("点击完 7，开始处理付款流程...")

            if check_and_handle_payment_success():
                # 如果检测到付款成功，执行确认还款检测
                print(f"开始检测 '{KEYWORD_CONFIRM}' ...")
                max_attempts = 5
                for attempt in range(1, max_attempts + 1):
                    print(f"第 {attempt} 次检测 '{KEYWORD_CONFIRM}' ...")
                    # 在数字键盘区域检测“确认还款”
                    confirm_candidates = local_ocr_paddle(KEYPAD_LEFT, KEYPAD_TOP, KEYPAD_RIGHT, KEYPAD_BOTTOM,
                                                          KEYWORD_CONFIRM)

                    if confirm_candidates:
                        confirm_selected = max(confirm_candidates, key=lambda c: c["score"])
                        confirm_x = KEYPAD_LEFT + confirm_selected["cx"]
                        confirm_y = KEYPAD_TOP + confirm_selected["cy"]
                        print(f"点击 '{KEYWORD_CONFIRM}'：({confirm_x:.1f}, {confirm_y:.1f})")

                        pyautogui.mouseDown(confirm_x, confirm_y)
                        time.sleep(CLICK_DURATION)
                        pyautogui.mouseUp(confirm_x, confirm_y)
                        break  # 点击成功，退出尝试
                    else:
                        print(f"未检测到 '{KEYWORD_CONFIRM}'，等待1秒后重试...")
                        time.sleep(1)
            else:
                # N秒内没检测到付款成功，直接返回继续检测"立减"
                print(f"未检测到 {KEYWORD_SUCCESS}，返回主循环...")
                return  # 退出数字点击函数


def get_screen_region() -> Tuple[int, int, int, int]:
    """获取固定的监控区域"""
    left, top, right, bottom = MONITOR_AREA
    print(f"使用固定截取区域：({left}, {top}) 到 ({right}, {bottom})")
    return left, top, right, bottom


def hold_and_slide_to_left(start_x: float, start_y: float, distance: int, steps: int = 10, step_duration: float = 0.01):
    """
    模拟人类滑动，从(start_x, start_y)开始向左滑动 distance 距离。
    带有轻微的Y轴随机摆动。
    """
    pyautogui.click(start_x, start_y)  # 先点击确保激活
    pyautogui.mouseDown()
    time.sleep(0.2)  # 按下后短暂保持

    step_x = distance / steps
    current_x = start_x
    current_y = start_y

    for _ in range(steps):
        current_x -= step_x
        # 模拟Y轴轻微抖动
        current_y = start_y + random.randint(-3, 3)
        pyautogui.moveTo(current_x, current_y, duration=step_duration)

    pyautogui.mouseUp()
    print(f"滑动完成：从 {start_x:.0f} 到 {current_x:.0f} (距离 {distance})")


# -----------------------------------------------------------------
# 主监控循环
# -----------------------------------------------------------------

def start_monitoring():
    """启动主监控循环"""
    global slide_distance_counter  # 声明使用全局变量来修改它

    left, top, right, bottom = get_screen_region()

    while True:
        try:
            # 1. 检测 "立减"
            print(f"开始检测 '{KEYWORD_PAYMENT}'...")
            candidates_payment = local_ocr_paddle(left, top, right, bottom, KEYWORD_PAYMENT)
            if candidates_payment:
                selected = candidates_payment[0]  # 默认选第一个
                click_x = left + selected["cx"] - 10  # X坐标微调
                click_y = top + selected["cy"] + 15  # Y坐标微调

                print(f"已点击 '{KEYWORD_PAYMENT}'：({click_x:.1f}, {click_y:.1f})")
                pyautogui.mouseDown(click_x, click_y)
                time.sleep(CLICK_DURATION)
                pyautogui.mouseUp(click_x, click_y)

                time.sleep(1)  # 点击后等待1秒，确保数字键盘弹出

                # 执行数字输入流程
                click_sequence_numbers(NUMBERS_TO_CLICK)

                print("完成数字点击流程，休眠 5 秒后继续...")
                time.sleep(5)
                continue  # 完成一轮，重新开始循环

            # 2. 检测 "的小荷包"
            print(f"未检测到 '{KEYWORD_PAYMENT}'，检测 '{KEYWORD_WALLET}'...")
            candidates_wallet = local_ocr_paddle(left, top, right, bottom, KEYWORD_WALLET)
            if candidates_wallet:
                selected = candidates_wallet[0]  # 默认选第一个
                click_x = left + selected["cx"]
                click_y = top + selected["cy"]

                print(f"已点击 '{KEYWORD_WALLET}'：({click_x:.1f}, {click_y:.1f})")
                pyautogui.mouseDown(click_x, click_y)
                time.sleep(CLICK_DURATION)
                pyautogui.mouseUp(click_x, click_y)

                time.sleep(0.5)  # 点击后等待0.5秒再拖动

                # 使用当前滑动距离并递增
                current_slide_distance = slide_distance_counter
                print(f"当前滑动距离：{current_slide_distance} 像素")
                hold_and_slide_to_left(click_x, click_y, current_slide_distance)

                # 更新下一次的滑动距离
                if slide_distance_counter >= 1900:
                    slide_distance_counter = 600  # 重置
                    print("滑动距离达到上限，重置为 600 像素")
                else:
                    slide_distance_counter += 100  # 递增
                    print(f"下一次滑动距离将增加为：{slide_distance_counter} 像素")

                print("滑动完成，继续检测...")
                # 这里不需要continue，让它走完下面的 time.sleep(1)

            else:
                print(f"未检测到 '{KEYWORD_WALLET}'，等待1秒后继续...")

            # 每轮检测间隔
            time.sleep(1)

        except Exception as e:
            print(f"发生未预料的错误: {e}")
            print("程序将在5秒后重启监控...")
            time.sleep(5)


# -----------------------------------------------------------------
# 程序入口
# -----------------------------------------------------------------
if __name__ == "__main__":
    print("自动化脚本启动...")
    start_monitoring()