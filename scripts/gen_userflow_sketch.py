"""
EmoEating — User Flow Sketch Diagram Generator
Outputs: paper/figures/emoeating_userflow_sketch.png
Purpose: Single-page workflow sketch for graphic designers (UIST 2026 teaser)
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

# ── Color palette ──────────────────────────────────────────────────────────
C = {
    'Q1':     '#F59E0B',   # Positive-Active (amber)
    'Q2':     '#EF4444',   # Negative-Active (red)
    'Q3':     '#3B82F6',   # Negative-Deactive (blue)
    'Q4':     '#10B981',   # Neutral/Calm (teal)
    'primary':'#2563EB',
    'enms':   '#1E40AF',   # deep blue for ENMS badge
    'text':   '#1E293B',
    'muted':  '#64748B',
    'border': '#E2E8F0',
    'bg':     '#F8FAFC',
    'white':  '#FFFFFF',
    'carb':   '#F59E0B',
    'prot':   '#3B82F6',
    'fat':    '#06B6D4',
}


def setup_figure():
    fig = plt.figure(figsize=(15, 24))
    ax = fig.add_axes([0.03, 0.02, 0.94, 0.96])
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 24)
    ax.axis('off')
    fig.patch.set_facecolor(C['bg'])
    ax.set_facecolor(C['bg'])
    return fig, ax


def rbox(ax, x, y, w, h, fc=None, ec=None, lw=1.5, ls='-', pad=0.15, zorder=2):
    fc = fc or C['white']
    ec = ec or C['border']
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad={pad}",
                       facecolor=fc, edgecolor=ec,
                       linewidth=lw, linestyle=ls, zorder=zorder)
    ax.add_patch(p)
    return p


def pill(ax, cx, cy, w, h, fc, ec, text, tsz=8, tc='white', zorder=4):
    p = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                       boxstyle="round,pad=0.08",
                       facecolor=fc, edgecolor=ec,
                       linewidth=1.2, zorder=zorder)
    ax.add_patch(p)
    ax.text(cx, cy, text, fontsize=tsz, color=tc,
            ha='center', va='center', fontweight='bold', zorder=zorder+1)


def arrow(ax, x1, y1, x2, y2, color=None, lw=2.2, style='->', rad=0.0):
    color = color or C['muted']
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle=style, color=color, lw=lw,
                    connectionstyle=f'arc3,rad={rad}'
                ), zorder=5)


def txt(ax, x, y, s, sz=10, c=None, ha='center', va='center', w='normal', i='normal', zorder=6):
    c = c or C['text']
    ax.text(x, y, s, fontsize=sz, color=c, ha=ha, va=va,
            fontweight=w, fontstyle=i, zorder=zorder)


def hbar(ax, x, y, total_w, fill_frac, color, h=0.18):
    ax.add_patch(FancyBboxPatch((x, y - h/2), total_w, h,
                                boxstyle="round,pad=0.03",
                                facecolor=C['border'], edgecolor='none', zorder=3))
    ax.add_patch(FancyBboxPatch((x, y - h/2), total_w * fill_frac, h,
                                boxstyle="round,pad=0.03",
                                facecolor=color, edgecolor='none', zorder=4))


def numbered_circle(ax, cx, cy, num_str, color, r=0.32):
    circle = plt.Circle((cx, cy), r, color=color, zorder=4)
    ax.add_patch(circle)
    txt(ax, cx, cy, num_str, sz=11, c='white', w='bold', zorder=5)


def draw(ax):

    # ─────────────────────────────────────────────────────────────────────
    # TITLE BLOCK
    # ─────────────────────────────────────────────────────────────────────
    txt(ax, 7.5, 23.5, 'EmoEating', sz=20, w='bold', c=C['primary'])
    txt(ax, 7.5, 23.05,
        'User Interaction Flow  |  Single Sketch for Graphic Designers  |  UIST 2026',
        sz=9.5, c=C['muted'])
    ax.plot([0.5, 14.5], [22.78, 22.78], color=C['border'], lw=1.5)

    # ─────────────────────────────────────────────────────────────────────
    # STEP 1 — LANDING / CONSENT
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 3.8, 21.45, 7.4, 1.1, fc='#EFF6FF', ec=C['primary'], lw=2.0)
    txt(ax, 7.5, 22.3, 'STEP 1 — Landing & Consent', sz=11.5, w='bold', c=C['primary'])
    txt(ax, 7.5, 21.95,
        'Research ethics notice  ->  Consent checkbox  ->  "Start" button',
        sz=9, c=C['muted'])
    txt(ax, 7.5, 21.65,
        'Assigns anonymous session token (UUID) on consent',
        sz=8.5, c=C['muted'], i='italic')

    arrow(ax, 7.5, 21.45, 7.5, 20.95)

    # ─────────────────────────────────────────────────────────────────────
    # STEP 2 — PROFILE (Optional)
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 3.0, 19.75, 9.0, 1.1, fc=C['white'], ec=C['muted'], lw=1.5, ls='--')
    pill(ax, 4.35, 20.62, 1.6, 0.3, fc='#F1F5F9', ec=C['muted'],
         text='OPTIONAL', tsz=7.5, tc=C['muted'])
    txt(ax, 7.5, 20.62, 'STEP 2 — Physiological Profile', sz=11, w='bold', c=C['text'])
    txt(ax, 7.5, 20.3,
        'Age  |  Sex  |  Height  |  Weight  |  Activity level  |  Meal type  |  Dietary restrictions',
        sz=8.5, c=C['muted'])
    txt(ax, 7.5, 20.0,
        'Computes:  BMI  |  BMR  |  TDEE  |  Meal calorie target (% of daily)',
        sz=8.5, c=C['text'], i='italic')

    # Skip path
    ax.annotate('', xy=(12.2, 17.0), xytext=(12.2, 19.75),
                arrowprops=dict(arrowstyle='->', color=C['muted'], lw=1.2,
                                linestyle='dashed',
                                connectionstyle='arc3,rad=-0.3'), zorder=3)
    txt(ax, 13.15, 18.5, 'skip\n(optional)', sz=8, c=C['muted'], i='italic')

    arrow(ax, 7.5, 19.75, 7.5, 19.2)

    # ─────────────────────────────────────────────────────────────────────
    # STEP 3 — EMOTION DETECTION (Core contribution — largest block)
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 0.6, 14.5, 13.8, 4.6, fc='#FFFBEB', ec='#F97316', lw=2.5)
    txt(ax, 6.8, 18.92, 'STEP 3 — Emotion Detection', sz=12, w='bold', c='#C2410C')
    pill(ax, 11.5, 18.92, 2.8, 0.38, fc='#F97316', ec='#F97316',
         text='* CORE CONTRIBUTION', tsz=8, tc='white')

    # ── PATH A: Voice ──────────────────────────────────────────────────
    rbox(ax, 0.8, 15.6, 5.6, 3.05, fc='#FEFCE8', ec='#EAB308', lw=1.8)
    txt(ax, 3.6, 18.45, 'PATH A — Voice  (Primary)', sz=10, w='bold', c='#92400E')
    txt(ax, 3.6, 18.15, '[Voice Recorder]  Record 3-5 sec of natural speech', sz=9, c=C['text'])
    txt(ax, 3.6, 17.87,
        'Prompt: "Kids are talking by the door."',
        sz=8.5, c=C['muted'], i='italic')
    txt(ax, 3.6, 17.58,
        'SER Model: emotion2vec_plus_large (FunASR)',
        sz=8.5, c=C['text'])
    txt(ax, 3.6, 17.32,
        '9-class softmax probability output',
        sz=8.5, c=C['text'])

    # Mini probability bars
    emotions_ex = [
        ('Stressed', 0.62, C['Q2']),
        ('Sad',      0.14, C['Q3']),
        ('Angry',    0.11, C['Q2']),
        ('Happy',    0.05, C['Q1']),
    ]
    for i, (emo, val, col) in enumerate(emotions_ex):
        ey = 16.95 - i * 0.27
        txt(ax, 1.55, ey, emo, sz=7.5, c=C['muted'], ha='right')
        hbar(ax, 1.6, ey, 3.5, val, col, h=0.16)
        txt(ax, 5.3, ey, f'{int(val*100)}%', sz=7.5, c=col, w='bold')

    txt(ax, 3.6, 15.85,
        'argmax -> top emotion -> zone  (bypasses VA step)',
        sz=8, c=C['muted'], i='italic')
    txt(ax, 3.6, 15.63, '[ Use voice result ]   [ Re-record ]', sz=8.5, c=C['primary'])

    # ── OR divider ──
    rbox(ax, 6.6, 16.8, 0.8, 0.5, fc=C['border'], ec=C['border'], lw=0, pad=0.1)
    txt(ax, 7.0, 17.05, 'OR', sz=10, w='bold', c=C['muted'])

    # ── PATH B: Manual ──────────────────────────────────────────────────
    rbox(ax, 8.6, 15.6, 5.6, 3.05, fc='#F0FDF4', ec='#22C55E', lw=1.8)
    txt(ax, 11.4, 18.45, 'PATH B — Manual  (Fallback)', sz=10, w='bold', c='#166534')
    txt(ax, 11.4, 18.15, '11-emotion affect grid', sz=9, c=C['text'])

    # Emotion grid — text only, two rows
    emotions_row1 = ['Happy', 'Excited', 'Calm', 'Peaceful', 'Neutral']
    emotions_row2 = ['Anxious', 'Stressed', 'Angry', 'Frustrated', 'Sad', 'Tired']
    for j, emo in enumerate(emotions_row1):
        ex = 9.05 + j * 1.05
        rbox(ax, ex - 0.44, 17.63, 0.88, 0.33, fc=C['white'], ec=C['border'], lw=0.8, pad=0.05)
        txt(ax, ex, 17.80, emo, sz=6.8, c=C['text'])
    for j, emo in enumerate(emotions_row2):
        ex = 8.82 + j * 0.92
        rbox(ax, ex - 0.4, 17.24, 0.82, 0.33, fc=C['white'], ec=C['border'], lw=0.8, pad=0.05)
        txt(ax, ex, 17.41, emo, sz=6.5, c=C['text'])

    txt(ax, 11.4, 17.0,
        'Select -> Valence / Arousal coordinates',
        sz=8.5, c=C['muted'])
    txt(ax, 11.4, 16.74,
        '(mapped via Russell Circumplex theory)',
        sz=8, c=C['muted'])
    txt(ax, 11.4, 16.48,
        'e.g. "Stressed"  ->  V = -0.55,  A = +0.70',
        sz=8.5, c=C['text'], i='italic')

    # Mini V-A plane
    ax.add_patch(FancyBboxPatch((9.1, 15.65), 4.6, 0.7,
                                boxstyle='round,pad=0.05', facecolor=C['white'],
                                edgecolor=C['border'], lw=1.0, zorder=3))
    for (fx, fy, fw, fh, fc2) in [
        (9.1,  16.0,  2.3, 0.35, C['Q2'] + '33'),
        (11.4, 16.0,  2.3, 0.35, C['Q1'] + '33'),
        (9.1,  15.65, 2.3, 0.35, C['Q3'] + '33'),
        (11.4, 15.65, 2.3, 0.35, C['Q4'] + '33'),
    ]:
        ax.add_patch(FancyBboxPatch((fx, fy), fw, fh,
                                   boxstyle='square,pad=0', facecolor=fc2,
                                   edgecolor='none', zorder=3))
    ax.plot([11.4, 11.4], [15.65, 16.35], color='white', lw=1.5, zorder=4)
    ax.plot([9.1, 13.7], [16.0, 16.0],   color='white', lw=1.5, zorder=4)
    ax.scatter([10.3], [16.2], color=C['Q2'], s=55, zorder=5)
    txt(ax, 10.55, 16.22, 'Stressed', sz=6.5, c=C['Q2'], w='bold', ha='left')

    # Converge arrows
    arrow(ax, 3.6, 15.6, 5.8, 15.0, color='#F97316', lw=1.8)
    arrow(ax, 11.4, 15.6, 9.2, 15.0, color='#22C55E', lw=1.8)

    # ── Zone classification row ──────────────────────────────────────────
    rbox(ax, 1.5, 14.55, 12.0, 0.95, fc=C['white'], ec=C['border'], lw=1.5)
    txt(ax, 7.5, 15.22,
        'Russell Circumplex Model  ->  4-Zone Classification',
        sz=10, w='bold', c=C['text'])
    zone_pills = [
        ('Q1  Pos-Active',    C['Q1'],  2.9),
        ('Q2  Neg-Active',    C['Q2'],  5.7),
        ('Q3  Neg-Deactive',  C['Q3'],  8.8),
        ('Q4  Neutral/Calm',  C['Q4'], 12.1),
    ]
    for label, col, cx in zone_pills:
        pill(ax, cx, 14.82, 2.3, 0.32, fc=col + '33', ec=col,
             text=label, tsz=8, tc=col)
    txt(ax, 7.5, 14.62,
        'Confidence slider (1-5)  |  [ Get Recommendations -> ]',
        sz=8.5, c=C['muted'])

    arrow(ax, 7.5, 14.5, 7.5, 14.05)

    # ─────────────────────────────────────────────────────────────────────
    # STEP 4 — ENMS ENGINE
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 0.6, 11.5, 13.8, 2.45, fc='#EEF2FF', ec='#6366F1', lw=2.5)
    txt(ax, 6.8, 13.75, 'STEP 4 — ENMS Scoring Engine', sz=12, w='bold', c='#4338CA')
    pill(ax, 11.65, 13.75, 3.2, 0.38, fc='#6366F1', ec='#6366F1',
         text='* TECHNICAL CONTRIBUTION', tsz=8, tc='white')

    txt(ax, 7.5, 13.38,
        'Nutritional Need Vector:  zone-specific macro ratios  +  priority micronutrients per emotional zone',
        sz=9, c=C['text'])

    # Formula box
    ax.add_patch(FancyBboxPatch((2.5, 12.72), 10.0, 0.52,
                                boxstyle="round,pad=0.1", facecolor='#312E81',
                                edgecolor='none', zorder=3))
    txt(ax, 7.5, 12.98,
        'ENMS  =  0.55 x macro_score  +  0.20 x micro_score  +  0.25 x pref_score',
        sz=10.5, c='white', w='bold')

    for cx, label, sub in [
        (3.8,  '55%  Macros',
         'carb / prot / fat\nvs. zone targets'),
        (7.5,  '20%  Micros',
         'priority vitamins & minerals\nper emotional zone'),
        (11.8, '25%  Preference',
         'user history\n(starts neutral)'),
    ]:
        txt(ax, cx, 12.38, label, sz=9, c='#4338CA', w='bold')
        txt(ax, cx, 12.05, sub, sz=8, c=C['muted'])

    txt(ax, 7.5, 11.7,
        'Zone macro ratios (guide §4.1) — e.g. Neg-Active:  Carb 52%  |  Prot 22%  |  Fat 26%',
        sz=8.5, c=C['muted'], i='italic')

    arrow(ax, 7.5, 11.5, 7.5, 11.05)

    # ─────────────────────────────────────────────────────────────────────
    # STEP 5 — RECOMMENDATIONS PAGE
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 0.6, 7.8, 13.8, 3.15, fc=C['white'], ec=C['border'], lw=2.0)
    txt(ax, 7.5, 10.76, 'STEP 5 — Recommendations Page', sz=12, w='bold', c=C['text'])

    # LEFT panel
    rbox(ax, 0.8, 7.9, 5.2, 2.65, fc='#F8FAFC', ec=C['border'], lw=1.2)
    txt(ax, 3.4, 10.36, 'Left Panel — Context', sz=9.5, w='bold', c=C['text'])
    txt(ax, 3.4, 10.08, '[Stressed]  Neg-Active Zone', sz=9, c=C['Q2'], w='bold')
    txt(ax, 3.4, 9.8, 'Macro targets (from Need Vector):', sz=8.5, c=C['text'])

    for i, (label, col, frac, val) in enumerate([
        ('Carbs',   C['carb'], 0.52, '90 g'),
        ('Protein', C['prot'], 0.22, '38 g'),
        ('Fat',     C['fat'],  0.26, '25 g'),
    ]):
        ey = 9.45 - i * 0.38
        txt(ax, 1.45, ey, label, sz=8, c=col, ha='right', w='bold')
        hbar(ax, 1.5, ey, 3.8, frac, col, h=0.2)
        txt(ax, 5.45, ey, val, sz=8, c=col, w='bold', ha='left')

    txt(ax, 3.4, 8.38, 'Priority micros: [ Mg ] [ Vit B6 ] [ Vit C ]', sz=8.5, c=C['muted'])
    txt(ax, 3.4, 8.12,
        '"Mg + B6 regulate cortisol in high-stress states"',
        sz=8, c=C['muted'], i='italic')
    txt(ax, 3.4, 7.92,
        '(peer-reviewed literature)',
        sz=7.5, c=C['muted'], i='italic')

    # RIGHT panel
    rbox(ax, 6.2, 7.9, 8.1, 2.65, fc='#F8FAFC', ec=C['border'], lw=1.2)
    txt(ax, 10.25, 10.36,
        'Right Panel — Top 3 Meal Cards (ranked by ENMS)',
        sz=9.5, w='bold', c=C['text'])

    card_data = [
        ('#1', 'Grilled Salmon  +  Quinoa',            '0.89', '520 kcal', C['Q1']),
        ('#2', 'Lentil Soup  +  Whole Grain Bread',    '0.81', '380 kcal', C['Q4']),
        ('#3', 'Turkey  &  Vegetable Stir-fry',        '0.74', '450 kcal', C['Q2']),
    ]
    for i, (rank, name, enms_val, kcal, col) in enumerate(card_data):
        cy = 9.95 - i * 0.65
        rbox(ax, 6.4, cy - 0.27, 7.7, 0.52, fc=C['white'], ec=C['border'], lw=1.0, pad=0.08)
        txt(ax, 7.05, cy, rank, sz=11, w='bold', c=col, ha='center')
        txt(ax, 9.4, cy + 0.1, name, sz=9, c=C['text'], ha='left', va='center')
        txt(ax, 9.4, cy - 0.12,
            f'{kcal}  |  macro bars  |  micro coverage  |  dietary flags',
            sz=7.5, c=C['muted'], ha='left', va='center')
        ax.add_patch(FancyBboxPatch((12.8, cy - 0.18), 1.2, 0.38,
                                   boxstyle='round,pad=0.06', facecolor=C['enms'],
                                   edgecolor='none', zorder=4))
        txt(ax, 13.4, cy, f'ENMS\n{enms_val}', sz=8, c='white', w='bold')

    txt(ax, 10.25, 8.05,
        'Each card: food photos (3-col grid)  |  full nutrient table  |  ingredient list  |  prep time',
        sz=8, c=C['muted'])

    arrow(ax, 7.5, 7.8, 7.5, 7.35)

    # ─────────────────────────────────────────────────────────────────────
    # OPTIONAL: RESTAURANT DISCOVERY
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 2.5, 6.4, 10.0, 0.87, fc=C['white'], ec=C['muted'], lw=1.2, ls='--')
    pill(ax, 3.85, 6.98, 1.6, 0.3, fc='#F1F5F9', ec=C['muted'],
         text='OPTIONAL', tsz=7.5, tc=C['muted'])
    txt(ax, 8.2, 6.98, 'Step 5b — Nearby Restaurant Discovery', sz=10, w='bold', c=C['muted'])
    txt(ax, 7.5, 6.65,
        '[Location]  City / GPS  ->  Google Places API  ->  3 cards per dish  |  11 km radius  |  session-only',
        sz=8.5, c=C['muted'])

    arrow(ax, 7.5, 6.4, 7.5, 5.97)

    # ─────────────────────────────────────────────────────────────────────
    # USER SELECTS MEAL
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 3.0, 5.35, 9.0, 0.55, fc='#F0FDF4', ec='#22C55E', lw=2.0)
    txt(ax, 7.5, 5.77,
        'User Selects Meal  ->  "I ate it"  ->  Session logged to research DB',
        sz=10, w='bold', c='#166534')
    txt(ax, 7.5, 5.52,
        'Anonymous:  session token  |  emotion  |  zone  |  ENMS score  |  food chosen',
        sz=8.5, c=C['muted'])

    # ─────────────────────────────────────────────────────────────────────
    # PAPER MAIN CONTRIBUTIONS (bottom dark panel)
    # ─────────────────────────────────────────────────────────────────────
    rbox(ax, 0.4, 0.4, 14.2, 4.75, fc='#1E293B', ec='#1E293B', lw=0, pad=0.3, zorder=2)
    txt(ax, 7.5, 4.9,
        'Paper Main Contributions  —  highlight in teaser figure',
        sz=11.5, w='bold', c='white')
    ax.plot([0.8, 14.2], [4.62, 4.62], color='#334155', lw=1.0)

    contribs = [
        ('1', 'Dual Emotion Input',
         'Voice SER (emotion2vec)\n+ Manual Affect Grid\n-> same zone pipeline',
         C['Q1'], 2.5),
        ('2', 'Russell Circumplex\n4-Zone Affective Model',
         'Q1 Pos-Active (amber)\nQ2 Neg-Active (red)\nQ3 Neg-Deactive (blue)\nQ4 Neutral (teal)',
         C['Q2'], 5.8),
        ('3', 'ENMS Scoring Formula',
         '3-component, fully auditable\n0.55 x macro + 0.20 x micro\n+ 0.25 x pref\nnot a black-box AI',
         '#6366F1', 9.1),
        ('4', 'Physiological\nPersonalization',
         'BMI  |  BMR  |  TDEE\n-> personal calorie target\n-> per-meal macro targets\n(optional but important)',
         C['Q4'], 12.4),
    ]
    for num, title, detail, col, cx in contribs:
        numbered_circle(ax, cx, 4.22, num, col)
        txt(ax, cx, 3.7, title, sz=9, c='white', w='bold')
        txt(ax, cx, 2.95, detail, sz=8, c='#94A3B8')

    ax.plot([0.8, 14.2], [2.08, 2.08], color='#334155', lw=1.0)
    txt(ax, 7.5, 1.82,
        '"Counter-hedonic design:  mood-supportive, not craving-matching"',
        sz=10.5, c='#E2E8F0', i='italic', w='bold')
    txt(ax, 7.5, 1.52,
        'Every recommendation is auditable to cited nutrition science — not a black-box AI',
        sz=9, c='#94A3B8')
    txt(ax, 7.5, 1.22,
        'ENMS  =  0.55 x macro_score  +  0.20 x micro_score  +  0.25 x pref_score   |   alpha + beta + gamma = 1.00',
        sz=9.5, c='#CBD5E1', w='bold')
    txt(ax, 7.5, 0.85,
        'RAVDESS voice prompt: "Kids are talking by the door."  (3-5 seconds)',
        sz=8.5, c='#64748B')
    txt(ax, 7.5, 0.58,
        'Contact: nvhnam01@gmail.com  |  Tagline: "Say how you feel. Eat what helps."',
        sz=8, c='#475569')


def main():
    fig, ax = setup_figure()
    draw(ax)

    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'paper', 'figures'
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'emoeating_userflow_sketch.png')

    plt.savefig(out_path, dpi=180, bbox_inches='tight',
                facecolor=C['bg'], edgecolor='none')
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == '__main__':
    main()
