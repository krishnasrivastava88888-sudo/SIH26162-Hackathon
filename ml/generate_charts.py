import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

OUTPUT_DIR = "ml/reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Feature Importance Chart
features = [
    "log_frp", "frp_thermal_ratio", "cluster_size",
    "brightness_k", "frp", "dist_fac_log",
    "diurnal_cycle_sin", "persistence_count_30d", "diurnal_cycle_cos"
]
importances = [0.2475, 0.2144, 0.1587, 0.1263, 0.1105, 0.0812, 0.0381, 0.0152, 0.0081]

plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

y_pos = np.arange(len(features))
colors = plt.cm.viridis(np.linspace(0.4, 0.9, len(features)))

bars = ax.barh(y_pos, importances[::-1], color=colors, edgecolor='none', height=0.6)
ax.set_yticks(y_pos)
ax.set_yticklabels(features[::-1], fontfamily='monospace', fontsize=10)
ax.set_xlabel('Gini Feature Importance', fontsize=11, fontweight='bold', labelpad=10)
ax.set_title('ThermoGuardAI | RF-v2.0 Feature Attribution', fontsize=13, fontweight='bold', pad=15)
ax.grid(axis='x', linestyle='--', alpha=0.2)

for bar in bars:
    width = bar.get_width()
    ax.text(width + 0.005, bar.get_y() + bar.get_height()/2, f'{width:.1%}', 
            va='center', fontsize=9, fontfamily='monospace', color='#A1A1AA')

plt.tight_layout()
feat_path = os.path.join(OUTPUT_DIR, "rf_v2_feature_importance.png")
plt.savefig(feat_path)
plt.close()
print(f" Saved feature importance chart: {feat_path}")

# 2. Confusion Matrix Plot
cm = np.array([
    [1368, 0, 0],
    [1, 15, 6],
    [0, 2, 2]
])
classes = ['Agricultural', 'Industrial Flare', 'Wildfire/Biomass']

fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=300)
sns.heatmap(cm, annot=True, fmt='d', cmap='mako', cbar=False,
            xticklabels=classes, yticklabels=classes,
            annot_kws={"size": 12, "weight": "bold"}, ax=ax)

ax.set_xlabel('Predicted Label', fontsize=11, fontweight='bold', labelpad=10)
ax.set_ylabel('Ground Truth Label', fontsize=11, fontweight='bold', labelpad=10)
ax.set_title('ThermoGuardAI | Spatial Test Split Confusion Matrix', fontsize=12, fontweight='bold', pad=15)

plt.tight_layout()
cm_path = os.path.join(OUTPUT_DIR, "rf_v2_confusion_matrix.png")
plt.savefig(cm_path)
plt.close()
print(f" Saved confusion matrix chart: {cm_path}")