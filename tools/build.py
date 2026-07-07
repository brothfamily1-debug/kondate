# -*- coding: utf-8 -*-
"""献立ページビルダー
data/sets_source.json（献立の選定）+ data/kasahara_recipes.json（レシピDB）
→ 買い物リストを集計して index.html を生成する。

使い方: リポジトリルートで  python3 tools/build.py
"""
import json, re, html, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db = json.load(open(f'{ROOT}/data/kasahara_recipes.json'))
src = json.load(open(f'{ROOT}/data/sets_source.json'))
byid = {r['id']: r for r in db}

# --- 買い物リスト分類 ---------------------------------------------------
STAPLE_PAT = re.compile(
    r'しょうゆ|醤油|みりん|^酒$|料理酒|砂糖|^塩$|塩\s|こしょう|コショウ|ペッパー|山椒|'
    r'だし|昆布茶|昆布|かつお節|削り節|煮干し|サラダ油|揚げ油|^油$|ごま油|ゴマ油|オリーブ|バター|'
    r'マヨネーズ|みそ|味噌|^酢$|黒酢|穀物酢|米酢|小麦粉|薄力粉|片栗粉|強力粉|パン粉|天ぷら粉|'
    r'ごま$|ゴマ|はちみつ|ハチミツ|ケチャップ|ソース$|めんつゆ|ポン酢|'
    r'^(おろし)?(にんにく|ニンニク)$|^(おろし)?(しょうが|ショウガ|生姜)(汁|のせん切り|のみじん切り)?$|'
    r'一味|七味|唐辛子|ゆずこしょう|わさび|からし|辛子|カラシ|'
    r'^米$|ご飯|ごはん|白飯|のり$|ノリ|海苔|わかめ|ワカメ|顆粒|鶏がらスープの素|チキンスープ|スープの素|'
    r'コンソメ|ナンプラー|オイスターソース|豆板醤|カレー粉|カレールー|おかか|合わせだし'
)
EXCLUDE_PAT = re.compile(r'^水$|^湯$|^熱湯$|^冷水$|^氷|お好みで|^あれば|^水溶き|^煮汁$')
ROLE = {'m': '主菜', 's': '副菜', 'j': '汁物', 'd': '一品'}


def strip_group(name):
    return re.sub(r'^[A-DＡ-Ｄ]\s*(\([^)]*\))?[:：]\s*', '', name).strip()


def agg_shopping(recipe_ids):
    buy, staple = {}, {}
    for rid in recipe_ids:
        for i in byid[rid]['ingredients']:
            name = strip_group(i['name'])
            if not name or EXCLUDE_PAT.search(name):
                continue
            key = re.sub(r'[\s　]', '', name)
            tgt = staple if STAPLE_PAT.search(name) else buy
            tgt.setdefault(key, {'name': name, 'amounts': []})
            if i['amount']:
                tgt[key]['amounts'].append(i['amount'])
    fmt = lambda d: [{'name': v['name'], 'amount': ' + '.join(v['amounts'][:3])} for v in d.values()]
    return fmt(buy), sorted(fmt(staple), key=lambda x: x['name'])


def build_set(s):
    ids = [d[0] for d in s['dishes']]
    missing = [i for i in ids if i not in byid]
    if missing:
        sys.exit(f'ERROR: 存在しないレシピID {missing} (セット: {s["name"]})')
    buy, staple = agg_shopping(ids)
    return {**{k: s.get(k) for k in ('week', 'day', 'name', 'time', 'note')},
            'weekend': s.get('weekend', s.get('time', 0) >= 40),
            'dishes': [{'id': i, 'role': ROLE[role], 'name': byid[i]['name'],
                        'url': byid[i]['url'], 'source': byid[i]['source'],
                        'servings': byid[i]['servings']} for i, role in s['dishes']],
            'buy': buy, 'staple': staple,
            'search_text': ' '.join([s['name']] + [byid[i]['name'] for i in ids] +
                                     [x['name'] for x in buy] + [x['name'] for x in staple])}


sets = {'dinner': [build_set(s) for s in src['dinner']],
        'lunch': [build_set(s) for s in src['lunch']]}
json.dump(sets, open(f'{ROOT}/data/kondate_sets.json', 'w'), ensure_ascii=False, indent=1)

# --- HTML描画 -----------------------------------------------------------
esc = lambda s: html.escape(str(s or ''), quote=True)


def dish_row(d):
    cls = {'主菜': 'main', '副菜': 'side', '汁物': 'soup', '一品': 'dish'}[d['role']]
    sv = f"<span class=\"sv\">{esc(d['servings'])}</span>" if d['servings'] else ''
    return (f'<li class="dish"><span class="role role-{cls}">{d["role"]}</span>'
            f'<a href="{esc(d["url"])}" target="_blank" rel="noopener">{esc(d["name"])}</a>'
            f'{sv}<span class="src">{esc(d["source"])}</span></li>')


def card(s, kind):
    daybadge = ''
    if s.get('day'):
        daybadge = f'<span class="day {"wknd" if s["weekend"] else ""}">{s["day"]}</span>'
    buy = ''.join(f'<li>{esc(x["name"])}<span class="amt">{esc(x["amount"])}</span></li>' for x in s['buy'])
    staple = '、'.join(esc(x['name']) for x in s['staple'])
    special = '<span class="tag-special">ごちそう</span>' if s['weekend'] and kind == 'dinner' else ''
    return f'''<article class="card" data-search="{esc(s['search_text'])}">
  <header class="card-head">{daybadge}<h3 class="set-name">{esc(s['name'])}</h3>
    <span class="time">約{s['time']}分</span>{special}</header>
  <ul class="dishes">{''.join(dish_row(d) for d in s['dishes'])}</ul>
  <p class="note">{esc(s['note'])}</p>
  <details class="shopping"><summary>買い物リスト（{len(s['buy'])}品）</summary>
    <ul class="buy">{buy}</ul>
    <p class="staple"><b>常備品チェック:</b> {staple}</p></details>
</article>'''


w1 = [s for s in sets['dinner'] if s['week'] == 1]
w2 = [s for s in sets['dinner'] if s['week'] == 2]
sections = f'''
<section id="w1" class="panel"><h2>晩ごはん <span class="wk-label">第1週</span></h2>
{''.join(card(s, 'dinner') for s in w1)}</section>
<section id="w2" class="panel"><h2>晩ごはん <span class="wk-label">第2週</span></h2>
{''.join(card(s, 'dinner') for s in w2)}</section>
<section id="lunch" class="panel"><h2>お昼ごはん <span class="wk-label">一品完結・順不同</span></h2>
{''.join(card(s, 'lunch') for s in sets['lunch'])}</section>'''

TEMPLATE = open(f'{ROOT}/tools/template.html', encoding='utf-8').read()
page = (TEMPLATE.replace('__SECTIONS__', sections)
                .replace('__PERIOD__', esc(src.get('period', '')))
                .replace('__CYCLE__', str(src.get('cycle', ''))))
open(f'{ROOT}/index.html', 'w', encoding='utf-8').write(page)
print(f"OK: index.html 生成 (第{src.get('cycle')}期 {src.get('period')} / 晩{len(sets['dinner'])}セット・昼{len(sets['lunch'])}品)")
