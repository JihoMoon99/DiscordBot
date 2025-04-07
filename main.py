# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time # time 추가
from zoneinfo import ZoneInfo
import os
import csv
import json
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm # 한글 폰트 설정 위해 추가
from dotenv import load_dotenv
from keep_alive import keep_alive

# ------------------ 한글 폰트 설정 (Replit 등 환경에 따라 경로 확인 필요) ------------------
# Replit 같은 환경에서는 기본 폰트가 없을 수 있으므로, 나눔고딕 같은 폰트 파일을 업로드하고 경로 지정
# 또는 시스템에 설치된 폰트 경로 사용
try:
    # 예시: NanumGothic.ttf 파일이 프로젝트 루트에 있다고 가정
    font_path = 'NanumGothic.ttf' # Replit의 파일 탐색기 최상위에 업로드하세요.
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rc('font', family='NanumGothic')
        plt.rc('axes', unicode_minus=False) # 마이너스 부호 깨짐 방지
        print(f"폰트 로드 성공: {font_path}")
    else:
        print(f"경고: 지정된 폰트 파일({font_path})을 찾을 수 없습니다. 기본 폰트를 사용합니다.")
        # 기본 폰트 사용 시 한글이 깨질 수 있음
except Exception as e:
    print(f"폰트 설정 중 오류 발생: {e}")


# ------------------ 초기 설정 ------------------
keep_alive() # Replit 유지용 웹서버 실행
load_dotenv() # .env 파일 로드

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True # 멤버 활동 상태 감지를 위해 (선택사항)

bot = commands.Bot(command_prefix='!', intents=intents)

# --- 데이터 파일 이름 정의 ---
DATA_FILE = 'user_data.json'
CSV_FILE = 'study_log.csv'
ATTENDANCE_FILE = 'attendance_log.json' # 출석 로그 파일

# --- 데이터 변수 초기화 ---
user_data = {}
attendance_log = {} # 메모리 내 출석 로그 (봇 재시작 시 파일에서 복원)

# --- 시간대 설정 함수 ---
def get_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))

# ------------------ 데이터 파일 관리 ------------------

# --- User Data ---
def save_user_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving user data: {e}")

def load_user_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        except json.JSONDecodeError:
            print(f"경고: {DATA_FILE}이 비어있거나 잘못된 형식입니다. 새 데이터 파일을 생성합니다.")
            user_data = {}
        except Exception as e:
            print(f"Error loading user data: {e}")
            user_data = {} # 오류 발생 시 빈 딕셔너리로 초기화
    else:
        user_data = {}

# --- Attendance Log ---
def save_attendance_log():
    try:
        # datetime 객체를 ISO 문자열로 변환하여 저장
        serializable_log = {}
        for uid, data in attendance_log.items():
            # data 딕셔너리 구조 확인 및 안전한 접근
            entry_time = data.get("입장")
            last_encouragement = data.get("마지막_격려")
            if entry_time and isinstance(entry_time, datetime): # datetime 객체인지 확인
                serializable_log[str(uid)] = {
                    "입장": entry_time.isoformat(),
                    "마지막_격려": last_encouragement if last_encouragement is not None else 0 # 기본값 처리
                }
            else:
                print(f"Warning: Invalid '입장' data for user {uid}: {entry_time}. Skipping save.")

        with open(ATTENDANCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving attendance log: {e}")


def load_attendance_log():
    global attendance_log
    if os.path.exists(ATTENDANCE_FILE):
        try:
            with open(ATTENDANCE_FILE, 'r', encoding='utf-8') as f:
                loaded_log = json.load(f)
                # ISO 문자열을 다시 datetime 객체로 변환하여 로드
                attendance_log = {}
                korea_tz = ZoneInfo("Asia/Seoul")
                for uid_str, data in loaded_log.items():
                    try:
                        # 타임존 정보가 포함된 ISO 문자열 파싱 시도
                        entry_time_str = data.get("입장")
                        last_encouragement = data.get("마지막_격려", 0) # 기본값 0

                        if not entry_time_str:
                            print(f"Warning: Missing '입장' data for user {uid_str}. Skipping entry.")
                            continue

                        entry_time = datetime.fromisoformat(entry_time_str)
                        # 만약 타임존 정보가 없다면 한국 시간대로 설정 (하위호환성)
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=korea_tz)
                        # 또는 항상 한국 시간대로 강제 변환
                        # entry_time = datetime.fromisoformat(data["입장"]).astimezone(korea_tz)

                        attendance_log[int(uid_str)] = {
                            "입장": entry_time,
                            "마지막_격려": last_encouragement
                        }
                    except (ValueError, TypeError) as dt_err:
                        print(f"Error parsing datetime for user {uid_str}: {dt_err}. Skipping entry.")
                    except Exception as inner_e:
                         print(f"Error processing attendance entry for user {uid_str}: {inner_e}. Skipping entry.")

        except json.JSONDecodeError:
            print(f"경고: {ATTENDANCE_FILE}이 비어있거나 잘못된 형식입니다. 새 로그 파일을 생성합니다.")
            attendance_log = {}
        except Exception as e:
            print(f"Error loading attendance log: {e}")
            attendance_log = {} # 오류 발생 시 빈 딕셔너리로 초기화
    else:
        attendance_log = {}

# --- 초기 데이터 로드 및 CSV 파일 준비 ---
load_user_data()
load_attendance_log() # 봇 시작 시 출석 로그 복원

if not os.path.exists(CSV_FILE):
    try:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f: # utf-8-sig for Excel compatibility
            writer = csv.writer(f)
            writer.writerow([
                'User ID', 'Username', 'Date', 'Start Time', 'End Time',
                'Duration (min)'
            ])
    except Exception as e:
        print(f"Error creating CSV file: {e}")

# ======================================================================
#                  자동화 태스크 정의 (on_ready 전에 위치해야 함)
# ======================================================================

# ------------------ 자동 격려 및 자동 퇴장 ------------------
@tasks.loop(minutes=10) # 루프 주기 (예: 10분마다)
async def encourage_message_loop():
    await bot.wait_until_ready() # 봇이 완전히 준비될 때까지 기다림
    now = get_now()
    # attendance_log 는 {uid: {"입장": datetime, "마지막_격려": int}} 형태
    to_remove = [] # 자동 퇴장 처리할 사용자 목록

    # 반복 중 딕셔너리 변경을 피하기 위해 키 목록 복사
    current_attendees = list(attendance_log.keys())

    for uid in current_attendees:
        if uid not in attendance_log: # 루프 도중 퇴장한 경우 건너뛰기
            continue

        info = attendance_log[uid]
        try:
            start_time = info.get("입장")
            last_encouragement = info.get("마지막_격려", 0)

            # 입장 시간이 유효한 datetime 객체인지 확인
            if not isinstance(start_time, datetime):
                 print(f"Warning: Invalid '입장' time found for user {uid} in encourage loop. Skipping.")
                 # 문제가 있는 데이터는 제거하는 것이 좋을 수 있음
                 # to_remove.append(uid)
                 continue

            duration_seconds = (now - start_time).total_seconds()
            duration_minutes = int(duration_seconds / 60)
            current_hours = duration_minutes // 60

            # --- 자동 퇴장 (6시간 = 360분) ---
            if duration_minutes >= 360:
                user = None
                try:
                     user = await bot.fetch_user(uid) # 사용자 객체 가져오기
                     if user:
                         await user.send(f"⏰ 6시간({duration_minutes}분)이 지나 자동 퇴장 처리되었습니다. 충분한 휴식도 중요해요! 내일도 파이팅! 💪")
                         print(f"자동 퇴장 처리: {user.name} ({uid}), 시간: {duration_minutes}분")
                     else: # fetch_user가 None을 반환할 수도 있음 (극히 드뭄)
                         print(f"자동 퇴장 처리 실패: 사용자 {uid} 객체를 가져올 수 없음")
                except discord.NotFound:
                     print(f"자동 퇴장 처리 실패: 사용자 {uid}를 찾을 수 없음 (서버 나감 등)")
                except discord.Forbidden:
                     print(f"자동 퇴장 처리 실패 (Forbidden): 사용자 {uid}에게 DM을 보낼 수 없음")
                except Exception as user_fetch_err:
                    print(f"자동 퇴장 중 사용자({uid}) 정보 조회/메시지 발송 오류: {user_fetch_err}")

                to_remove.append(uid)
                # 자동 퇴장 시에는 CSV/JSON 기록은 남기지 않음 (선택사항)

            # --- 격려 메시지 (1시간 단위) ---
            # 마지막 격려 시간보다 현재 경과 시간이 크면 발송
            elif current_hours > 0 and current_hours > last_encouragement:
                user = None
                try:
                    user = await bot.fetch_user(uid)
                    if user:
                        await user.send(f"🎉 와우! 공부 시작 {current_hours}시간 돌파! 정말 대단해요! 잠시 스트레칭은 어때요? 😊")
                        attendance_log[uid]["마지막_격려"] = current_hours # 격려 시간 업데이트
                        print(f"격려 메시지 발송: {user.name} ({uid}), 시간: {current_hours}시간")
                    else:
                         print(f"격려 메시지 발송 실패: 사용자 {uid} 객체를 가져올 수 없음")
                except discord.NotFound:
                     print(f"격려 메시지 발송 실패: 사용자 {uid}를 찾을 수 없음 (서버 나감 등)")
                except discord.Forbidden:
                     print(f"격려 메시지 발송 실패 (Forbidden): 사용자 {uid}에게 DM을 보낼 수 없음")
                     # DM 차단 시에도 격려 시간은 업데이트 할 지 결정 필요 (현재는 안 함)
                except Exception as user_fetch_err:
                     print(f"격려 메시지 발송 중 사용자({uid}) 정보 조회/메시지 발송 오류: {user_fetch_err}")


        except Exception as e:
            print(f"Error in encourage_message_loop for user {uid}: {e}")
            # 개별 사용자 오류가 전체 루프를 멈추지 않도록 처리

    # 자동 퇴장 처리된 사용자들 로그에서 제거 및 파일 업데이트
    if to_remove:
        changed = False
        for uid in to_remove:
            if uid in attendance_log:
                del attendance_log[uid]
                changed = True
        if changed:
            save_attendance_log() # 변경 사항이 있을 때만 저장

# ------------------ 주간 초기화 ------------------
# 매주 월요일 00:00 KST 에 실행
@tasks.loop(time=time(hour=0, minute=0, tzinfo=ZoneInfo("Asia/Seoul")))
async def weekly_reset_loop():
    await bot.wait_until_ready()
    now = get_now()
    # 정확히 월요일인지 확인
    if now.weekday() == 0:
        print(f"주간 기록 초기화 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        backup_data = {}
        users_to_reset = list(user_data.keys()) # 반복 중 변경 대비

        for uid_str in users_to_reset: # 키는 문자열이므로 uid_str 사용
            if uid_str in user_data and "weekly" in user_data[uid_str] and user_data[uid_str]["weekly"]:
                # 백업할 데이터가 있는 경우에만 백업
                backup_data[uid_str] = {
                    "username": user_data[uid_str].get("username", f"Unknown ({uid_str})"),
                    "weekly_data": user_data[uid_str]["weekly"]
                }
                user_data[uid_str]["weekly"] = {} # 해당 유저의 주간 기록 초기화

        # 백업 데이터 저장 (주차 정보 포함)
        if backup_data: # 백업할 내용이 있을 때만 파일 생성
            # 해당 주의 시작일(월요일)을 정확히 계산
            today = now.date()
            start_of_last_week = today - timedelta(days=today.weekday() + 7) # 지난주 월요일
            backup_filename = f"weekly_backup_{start_of_last_week.strftime('%Y-W%U')}.json"
            try:
                with open(backup_filename, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
                print(f"주간 기록 백업 완료: {backup_filename}")
            except Exception as e:
                 print(f"주간 기록 백업 실패: {e}")

        # 초기화된 user_data 저장
        save_user_data()
        print("✅ 주간 기록 초기화 완료")


# ------------------ 매일 저녁 8시 스터디 알림 (주중만) ------------------
# 매일 20:00 KST 에 실행되지만, 실제 알림은 주중에만 발송
@tasks.loop(time=time(hour=20, minute=0, tzinfo=ZoneInfo("Asia/Seoul")))
async def daily_study_reminder():
    await bot.wait_until_ready()
    # --- 오늘 요일 확인 ---
    now = get_now()
    # weekday()는 월요일이 0, 일요일이 6입니다. 0~4가 주중(월~금)입니다.
    if now.weekday() >= 5: # 5 이상이면 토요일 또는 일요일
        # 주말에는 알림을 보내지 않고 조용히 종료
        # print(f"{now.strftime('%Y-%m-%d %A')} - 주말이므로 스터디 알림을 건너<0xEB><0x9B><0x89>니다.") # 확인 로그 필요시 주석 해제
        return

    # --- 이하 로직은 주중(월~금)에만 실행됨 ---
    channel_id_str = os.getenv("STUDY_CHANNEL_ID")
    if not channel_id_str:
        print("환경 변수 'STUDY_CHANNEL_ID'가 설정되지 않았습니다. 스터디 알림을 보낼 수 없습니다.")
        return

    try:
        channel_id = int(channel_id_str)
        channel = bot.get_channel(channel_id)

        if channel and isinstance(channel, discord.TextChannel):
            active_users = len(attendance_log)
            message = (f"📢 저녁 8시입니다! 스터디 시작할 시간이에요.\n"
                       f"오늘도 목표를 향해 함께 달려봐요! `!입장`으로 시작하세요.\n"
                       f"(현재 {active_users}명 공부 중 🔥)")
            await channel.send(message)
            print(f"스터디 시작 알림 전송 완료 (채널: {channel.name}) - 주중 알림")
        else:
            print(f"스터디 알림 채널(ID: {channel_id})을 찾을 수 없거나 텍스트 채널이 아닙니다.")

    except ValueError:
         print(f"환경 변수 'STUDY_CHANNEL_ID'({channel_id_str})가 올바른 숫자 형식이 아닙니다.")
    except discord.Forbidden:
         print(f"스터디 알림 채널(ID: {channel_id})에 메시지를 보낼 권한이 없습니다.")
    except Exception as e:
        print(f"Error in daily_study_reminder: {e}")


# ------------------ 주간 요약 자동 DM ------------------
# 매주 토요일 08:00 KST 에 실행
@tasks.loop(time=time(hour=8, minute=0, tzinfo=ZoneInfo("Asia/Seoul")))
async def weekly_summary_dm():
    await bot.wait_until_ready()
    now = get_now()
    # 토요일(weekday 5)인지 확인
    if now.weekday() == 5:
        print(f"주간 요약 DM 발송 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        users_to_dm = list(user_data.keys()) # 반복 중 변경 대비

        for uid_str in users_to_dm:
            # weekly 데이터는 월요일 0시에 초기화되므로, 토요일 아침에는 '이번 주'의 데이터가 맞음.
            if uid_str not in user_data: continue # 혹시 모를 데이터 불일치

            data = user_data[uid_str]
            username = data.get("username", f"User {uid_str}") # 이름 가져오기
            weekly_data = data.get("weekly", {})

            if not weekly_data: # 이번 주 기록이 없으면 건너뛰기
                continue

            try:
                uid = int(uid_str) # DM 발송 위해 int로 변환
            except ValueError:
                print(f"Invalid user ID format found: {uid_str}. Skipping weekly summary.")
                continue

            # 날짜 기준으로 정렬
            try:
                sorted_weekly_data = dict(sorted(weekly_data.items()))
            except Exception as sort_err:
                print(f"Error sorting weekly data for user {uid_str}: {sort_err}. Skipping.")
                continue

            days = list(sorted_weekly_data.keys())
            values = list(sorted_weekly_data.values())
            weekly_sum = sum(values)

            # 데이터가 없을 경우 max() 오류 방지
            if not values:
                max_value = 0
            else:
                max_value = max(values) if max(values) > 0 else 60 # 최소 y축 높이 확보

            filename = f"weekly_summary_{uid_str}.png"
            try:
                # --- 시각화 차트 생성 ---
                plt.figure(figsize=(10, 5))
                bars = plt.bar(days, values, color='mediumpurple')
                plt.title(f"{username}님의 이번 주 공부 시간 요약", fontsize=16)
                plt.xlabel("날짜", fontsize=12)
                plt.ylabel("공부 시간 (분)", fontsize=12)
                plt.xticks(rotation=45, ha='right')
                plt.yticks(range(0, max_value + 60, 60)) # +60 해서 상단 여유 확보
                plt.grid(axis='y', linestyle='--', alpha=0.7)

                for bar in bars:
                    yval = bar.get_height()
                    if yval > 0:
                        plt.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center', fontsize=10)

                plt.tight_layout()
                plt.savefig(filename)
                plt.close() # 중요: plt 메모리 해제

                # --- DM 발송 ---
                user = None
                try:
                    user = await bot.fetch_user(uid)
                    if user:
                        summary_message = (f"📈 **{username}**님, 이번 주 공부 시간 요약입니다!\n"
                                           f" • 총 공부 시간: **{weekly_sum}분**\n"
                                           f"주말 잘 보내시고 다음 주도 파이팅이에요! 👍")
                        await user.send(summary_message, file=discord.File(filename))
                        print(f"주간 요약 DM 발송 성공: {username} ({uid})")
                    else:
                        print(f"주간 요약 DM 발송 실패: 사용자 {uid} 객체를 가져올 수 없음")
                except discord.NotFound:
                     print(f"주간 요약 DM 발송 실패: 사용자 {uid}를 찾을 수 없음 (서버 나감 등)")
                except discord.Forbidden: # DM 차단 등 권한 문제
                     print(f"주간 요약 DM 발송 실패 (Forbidden): {username} ({uid}). DM이 차단되었을 수 있습니다.")
                except Exception as dm_err:
                    print(f"Error sending weekly summary DM to {uid} ({username}): {dm_err}")

            except Exception as plot_err:
                print(f"Error generating plot or sending summary for user {uid_str}: {plot_err}")
                plt.close() # 오류 발생 시에도 plt 리소스 해제 시도
            finally:
                # 임시 파일 삭제
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except Exception as remove_err:
                        print(f"Error removing temp summary file {filename}: {remove_err}")

# ======================================================================
#                       봇 이벤트 및 명령어 정의
# ======================================================================

# ------------------ 봇 준비 ------------------
@bot.event
async def on_ready():
    print(f'{bot.user} 작동 시작!')
    print(f"현재 {len(attendance_log)}명의 사용자가 입장 상태입니다.")
    # 정의된 태스크 루프 시작
    encourage_message_loop.start()
    weekly_reset_loop.start()
    daily_study_reminder.start()
    weekly_summary_dm.start()
    print("자동화 작업 루프 시작됨.")


# ------------------ 입장 / 퇴장 ------------------
@bot.command(name="입장")
async def check_in(ctx):
    now = get_now()
    uid = ctx.author.id
    if uid in attendance_log:
        await ctx.send(f"{ctx.author.mention} 이미 입장 상태입니다. 퇴장 후 다시 시도해주세요.")
        return

    try:
        attendance_log[uid] = {"입장": now, "마지막_격려": 0}
        save_attendance_log() # 입장 시 파일 저장
        await ctx.send(
            f"{ctx.author.mention} 입장 시간 기록 완료! 🟢 {now.strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"Error in 입장 command for user {uid}: {e}")
        # 실패 시 메모리에서도 제거 시도 (선택적)
        if uid in attendance_log:
            del attendance_log[uid]
        await ctx.send("입장 기록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


@bot.command(name="퇴장")
async def check_out(ctx):
    now = get_now()
    uid = ctx.author.id

    if uid not in attendance_log:
        await ctx.send(f"{ctx.author.mention} 입장 기록이 없습니다. 먼저 `!입장`을 입력해주세요.")
        return

    try:
        # attendance_log 에는 datetime 객체가 저장되어 있음 (load 시 변환했으므로)
        start_time = attendance_log[uid].get("입장")

        # start_time 유효성 검사 (load 실패 등으로 없을 경우 대비)
        if not isinstance(start_time, datetime):
             print(f"Error in 퇴장: Invalid start_time for user {uid}. Log data: {attendance_log.get(uid)}")
             await ctx.send(f"{ctx.author.mention} 퇴장 처리 중 오류가 발생했습니다. (입장 시간 정보 오류)")
             # 문제가 있는 로그 제거
             if uid in attendance_log:
                 del attendance_log[uid]
                 save_attendance_log()
             return

        minutes = int((now - start_time).total_seconds() / 60)

        # 분이 음수인 경우 방지 (시스템 시간 변경 등 예외 상황)
        if minutes < 0: minutes = 0

        # 사용자 데이터 구조 초기화 (처음 기록 시)
        uid_str = str(uid) # JSON 키는 문자열이어야 함
        if uid_str not in user_data:
            user_data[uid_str] = {
                "username": str(ctx.author), # 사용자 이름도 저장
                "total": 0,
                "weekly": {},
                "daily": {},
                "monthly": {}
            }
        # 사용자 이름 업데이트 (닉네임 변경 대비)
        user_data[uid_str]["username"] = str(ctx.author)

        today_str = now.date().isoformat()
        month_str = now.strftime("%Y-%m")
        udata = user_data[uid_str]

        # 시간 누적 (없는 키 접근 방지 위해 .get 사용)
        udata["total"] = udata.get("total", 0) + minutes
        udata["weekly"] = udata.get("weekly", {})
        udata["daily"] = udata.get("daily", {})
        udata["monthly"] = udata.get("monthly", {})

        udata["weekly"][today_str] = udata["weekly"].get(today_str, 0) + minutes
        udata["daily"][today_str] = udata["daily"].get(today_str, 0) + minutes
        udata["monthly"][month_str] = udata["monthly"].get(month_str, 0) + minutes

        save_user_data() # 유저 데이터 저장

        # CSV 로그 기록
        try:
            with open(CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    uid, str(ctx.author), today_str,
                    start_time.strftime('%H:%M:%S'),
                    now.strftime('%H:%M:%S'), minutes
                ])
        except Exception as e:
            print(f"Error writing to CSV file: {e}")

        await ctx.send(
            f"{ctx.author.mention} 퇴장 기록 완료! 🔴 총 공부 시간: {minutes}분")

        # 출석 로그에서 제거 및 파일 저장
        del attendance_log[uid]
        save_attendance_log()

    except KeyError: # 혹시 모를 동시성 문제나 데이터 오류
         await ctx.send(f"{ctx.author.mention} 퇴장 처리 중 오류가 발생했습니다. (KeyError)")
         # 문제가 지속되면 로그 확인 필요
         if uid in attendance_log: # 안전하게 제거 시도
             del attendance_log[uid]
             save_attendance_log()
    except Exception as e:
        print(f"Error in 퇴장 command for user {uid}: {e}")
        await ctx.send("퇴장 기록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


# ------------------ 통계/시각화 (통합) ------------------
@bot.command(name="통계")
async def stats(ctx, 기간: str = "주간"):
    uid = str(ctx.author.id)
    now = get_now()
    기간 = 기간.lower() # 입력값 소문자 변환

    if uid not in user_data:
        await ctx.send(f"{ctx.author.mention} 아직 기록된 공부 시간이 없습니다.")
        return

    udata = user_data[uid]
    username = udata.get("username", ctx.author.display_name) # 저장된 이름 또는 현재 이름

    try:
        if 기간 == "일간":
            today_str = now.date().isoformat()
            daily_data = udata.get("daily", {})
            daily_minutes = daily_data.get(today_str, 0)
            await ctx.send(f"📅 **{username}**님의 오늘 공부 시간: **{daily_minutes}분**")

        elif 기간 == "월간":
            month_str = now.strftime("%Y-%m")
            monthly_data = udata.get("monthly", {})
            monthly_minutes = monthly_data.get(month_str, 0)
            await ctx.send(f"📆 **{username}**님의 이번 달 총 공부 시간: **{monthly_minutes}분**")

        elif 기간 == "주간":
            weekly_data = udata.get("weekly", {})
            weekly_sum = sum(weekly_data.values())
            total_sum = udata.get("total", 0)

            # --- 주간 시각화 생성 ---
            if not weekly_data:
                 # 주간 데이터가 없으면 텍스트만 전송
                 await ctx.send(f"📊 **{username}**님의 공부 통계\n"
                               f" • 총 누적 공부 시간: **{total_sum}분**\n"
                               f" • 이번 주 공부 시간: **{weekly_sum}분**\n"
                               f" 이번 주 기록이 아직 없습니다.")
                 return

            # 날짜 기준으로 정렬하여 시각화
            try:
                sorted_weekly_data = dict(sorted(weekly_data.items()))
            except Exception as sort_err:
                print(f"Error sorting weekly data for stats command (user {uid}): {sort_err}")
                await ctx.send("주간 통계 데이터 정렬 중 오류가 발생했습니다.")
                return

            days = list(sorted_weekly_data.keys())
            values = list(sorted_weekly_data.values())

            # 데이터가 없을 경우 max() 오류 방지
            if not values:
                max_value = 0
            else:
                max_value = max(values) if max(values) > 0 else 60 # 최소 y축 높이 확보

            filename = f"weekly_chart_{uid}.png"
            try:
                plt.figure(figsize=(10, 5)) # 크기 조정
                bars = plt.bar(days, values, color='skyblue') # 색상 지정
                plt.title(f"{username}님의 이번 주 공부 시간", fontsize=16)
                plt.xlabel("날짜", fontsize=12)
                plt.ylabel("공부 시간 (분)", fontsize=12)
                plt.xticks(rotation=45, ha='right') # 라벨 회전 및 정렬
                plt.yticks(range(0, max_value + 60, 60)) # y축 눈금 간격 조정 (+60으로 상단 여유)
                plt.grid(axis='y', linestyle='--', alpha=0.7) # 가로선 추가

                # 막대 위에 값 표시
                for bar in bars:
                    yval = bar.get_height()
                    if yval > 0: # 0 이상인 값만 표시
                        plt.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center', fontsize=10)

                plt.tight_layout() # 레이아웃 자동 조정
                plt.savefig(filename)
                plt.close() # 중요: plt 메모리 해제

                # 텍스트 메시지와 함께 파일 전송
                summary_message = (f"📊 **{username}**님의 공부 통계\n"
                                   f" • 총 누적 공부 시간: **{total_sum}분**\n"
                                   f" • 이번 주 총 공부 시간: **{weekly_sum}분**")
                await ctx.send(summary_message, file=discord.File(filename))

            except Exception as plot_err:
                print(f"Error generating plot for user {uid}: {plot_err}")
                plt.close() # 오류 발생 시에도 plt 리소스 해제 시도
                await ctx.send("주간 공부 시간 그래프 생성 중 오류가 발생했습니다.")
                # 오류 시에도 텍스트 통계는 보여주도록
                await ctx.send(f"📊 **{username}**님의 공부 통계\n"
                               f" • 총 누적 공부 시간: **{total_sum}분**\n"
                               f" • 이번 주 공부 시간: **{weekly_sum}분**")
            finally:
                # 파일 전송 성공 여부와 관계없이 임시 파일 삭제
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except Exception as remove_err:
                         print(f"Error removing temp file {filename}: {remove_err}")

        else:
            await ctx.send("잘못된 기간입니다. `!통계 [일간/주간/월간]` 또는 `!통계` 형식으로 입력해주세요.")

    except Exception as e:
        print(f"Error in 통계 command for user {uid}: {e}")
        await ctx.send("통계 조회 중 오류가 발생했습니다.")


# ------------------ 도움말 ------------------
@bot.command(name="도움말")
async def help_command(ctx):
    # Embed 사용 예시 (더 보기 좋게)
    embed = discord.Embed(title="📌 스터디 봇 명령어 안내", color=discord.Color.blue())
    embed.add_field(name="`!입장`", value="공부 시작 시간을 기록합니다.", inline=False)
    embed.add_field(name="`!퇴장`", value="공부 종료 시간을 기록하고, 공부 시간을 계산하여 저장합니다.", inline=False)
    embed.add_field(name="`!통계` 또는 `!통계 주간`", value="이번 주 공부 시간 통계와 그래프를 함께 보여줍니다.", inline=False)
    embed.add_field(name="`!통계 일간`", value="오늘의 공부 시간을 보여줍니다.", inline=False)
    embed.add_field(name="`!통계 월간`", value="이번 달의 총 공부 시간을 보여줍니다.", inline=False)
    embed.set_footer(text="괄호 안은 선택 옵션입니다. | 문의: [봇 개발자 또는 서버 관리자]") # 문의처 수정

    # 자동 기능 설명 추가
    embed.add_field(name="⏰ 자동 기능", value=(
        "• 1시간마다 공부 격려 메시지 발송 (DM)\n"
        "• 6시간 초과 시 자동 퇴장 처리 (DM 알림)\n"
        "• 매일 저녁 8시 스터디 시작 알림 (지정 채널, 주중만)\n" # 주중만 알림 명시
        "• 매주 월요일 00시 주간 기록 초기화 (백업 후 초기화)\n"
        "• 매주 토요일 오전 8시 주간 요약 리포트 발송 (DM, 그래프 포함)"
    ), inline=False)

    await ctx.send(embed=embed)

# ------------------ 오류 처리 ------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # 존재하지 않는 명령어 입력 시 조용히 무시하거나 안내 메시지 전송
        # await ctx.send(f"'{ctx.invoked_with}'는 존재하지 않는 명령어입니다. `!도움말`을 확인해주세요.")
        print(f"CommandNotFound: {ctx.message.content} by {ctx.author}") # 로그만 남기기
        return # 조용히 무시
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"명령어 사용법이 잘못되었습니다. '{ctx.command.name}' 명령어는 추가 정보가 필요합니다. `!도움말`을 확인해주세요.")
    elif isinstance(error, commands.BadArgument):
         await ctx.send(f"명령어에 잘못된 인자가 전달되었습니다. `!도움말`을 확인해주세요.")
    elif isinstance(error, commands.CheckFailure):
         await ctx.send("이 명령어를 실행할 권한이 없습니다.")
    elif isinstance(error, commands.CommandInvokeError):
         # 명령어 실행 자체에서 발생한 오류 (원본 오류 확인 가능)
         original = error.original
         print(f"CommandInvokeError in '{ctx.command.qualified_name}': {original}")
         # 특정 오류 타입에 따라 다른 메시지 표시 가능
         if isinstance(original, discord.Forbidden):
             await ctx.send("봇이 필요한 권한을 가지고 있지 않아 명령어를 실행할 수 없습니다. (예: 메시지 보내기, 파일 첨부 등)")
         elif isinstance(original, discord.HTTPException):
             await ctx.send("디스코드 API 통신 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.")
         else:
             await ctx.send("명령어 실행 중 내부 오류가 발생했습니다. 관리자에게 문의해주세요.")
    else:
        # 개발자가 확인해야 할 다른 모든 오류
        print(f"Unhandled error in command {ctx.command}: {error}")
        # 사용자에게 너무 자세한 오류 메시지는 노출하지 않는 것이 좋음
        await ctx.send("명령어 실행 중 예상치 못한 오류가 발생했습니다. 관리자에게 문의해주세요.")


# ------------------ 봇 실행 ------------------
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("오류: DISCORD_TOKEN 환경 변수를 찾을 수 없습니다. Replit의 Secrets 탭에 DISCORD_TOKEN을 추가해주세요.")
    else:
        try:
            bot.run(token)
        except discord.LoginFailure:
             print("오류: 잘못된 토큰입니다. DISCORD_TOKEN 환경 변수를 확인해주세요.")
        except discord.PrivilegedIntentsRequired:
             print("오류: Privileged Intents(members, presences)가 활성화되지 않았습니다.")
             print("Discord Developer Portal (https://discord.com/developers/applications)에서 해당 봇의 설정을 확인하고")
             print("'Privileged Gateway Intents' 섹션의 'PRESENCE INTENT'와 'SERVER MEMBERS INTENT'를 활성화해주세요.")
        except Exception as e:
             print(f"봇 실행 중 치명적인 오류 발생: {e}")