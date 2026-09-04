#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
永磁直流/无刷直流电机电磁分析工具 v6.0
===================================================
专业级轴向磁通永磁（AFPM）盘式无刷直流电机电磁计算与可视化工具

功能特性:
- 全面的磁路分析
- 反电动势计算（相电压和线电压）
- 电磁转矩及脉动分析
- 自感和互感估算
- 齿槽转矩解析估算
- 损耗分解（铜损、涡流损耗、机械损耗）
- 数据导出（JSON、CSV、TXT）和报告打印
- 交互式可视化界面

作者: 电机工程分析模块
版本: 6.0
许可证: MIT
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import numpy as np
import math
import json
import csv
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings

MATPLOTLIB_AVAILABLE = False
MATPLOTLIB_IMPORT_ERROR = None

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import matplotlib.patches as patches
    from matplotlib.gridspec import GridSpec
    MATPLOTLIB_AVAILABLE = True
except Exception as exc:  # pragma: no cover - exercised via import smoke tests
    plt = None
    FigureCanvasTkAgg = None
    NavigationToolbar2Tk = None
    Figure = None
    patches = None
    GridSpec = None
    MATPLOTLIB_IMPORT_ERROR = exc

# 设置中文字体
if MATPLOTLIB_AVAILABLE:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

# ==========================================
# 工程常数
# ==========================================
PI = math.pi
MU0 = 4 * PI * 1e-7  # 真空磁导率 (H/m)

# 铜材料属性
RHO_CU_20 = 1.72e-8  # 20°C时电阻率 (Ω·m)
RHO_CU_TEMP_COEFF = 0.00393  # 温度系数 (1/K)
ALPHA_CU = 0.00393

# 空气属性
AIR_DENSITY = 1.225  # 海平面空气密度 kg/m³

# ==========================================
# 材料库
# ==========================================
MAGNET_LIBRARY = {
    "N35": {"Br": 1.17, "Hc": 868, "BHmax": 263, "Tmax": 80, "描述": "标准级钕铁硼"},
    "N38": {"Br": 1.22, "Hc": 899, "BHmax": 287, "Tmax": 80, "描述": "标准级钕铁硼"},
    "N40": {"Br": 1.25, "Hc": 923, "BHmax": 302, "Tmax": 80, "描述": "标准级钕铁硼"},
    "N42": {"Br": 1.28, "Hc": 955, "BHmax": 318, "Tmax": 80, "描述": "高性能钕铁硼"},
    "N45": {"Br": 1.32, "Hc": 995, "BHmax": 342, "Tmax": 80, "描述": "高性能钕铁硼"},
    "N48": {"Br": 1.38, "Hc": 1027, "BHmax": 366, "Tmax": 80, "描述": "超高性能钕铁硼"},
    "N50": {"Br": 1.40, "Hc": 1043, "BHmax": 382, "Tmax": 80, "描述": "超高性能钕铁硼"},
    "N52": {"Br": 1.43, "Hc": 1059, "BHmax": 398, "Tmax": 80, "描述": "顶级钕铁硼"},
    "N35SH": {"Br": 1.17, "Hc": 876, "BHmax": 263, "Tmax": 150, "描述": "高温级钕铁硼"},
    "N38SH": {"Br": 1.22, "Hc": 907, "BHmax": 287, "Tmax": 150, "描述": "高温级钕铁硼"},
    "N42SH": {"Br": 1.28, "Hc": 955, "BHmax": 318, "Tmax": 150, "描述": "高温级钕铁硼"},
    "SmCo28": {"Br": 1.05, "Hc": 796, "BHmax": 210, "Tmax": 300, "描述": "钐钴永磁"},
    "SmCo32": {"Br": 1.13, "Hc": 860, "BHmax": 255, "Tmax": 300, "描述": "钐钴永磁"},
}

WIRE_AWG_TABLE = {
    "AWG10": {"直径_mm": 2.588, "截面积_mm2": 5.26},
    "AWG12": {"直径_mm": 2.053, "截面积_mm2": 3.31},
    "AWG14": {"直径_mm": 1.628, "截面积_mm2": 2.08},
    "AWG16": {"直径_mm": 1.291, "截面积_mm2": 1.31},
    "AWG18": {"直径_mm": 1.024, "截面积_mm2": 0.823},
    "AWG20": {"直径_mm": 0.812, "截面积_mm2": 0.518},
    "AWG22": {"直径_mm": 0.644, "截面积_mm2": 0.326},
    "AWG24": {"直径_mm": 0.511, "截面积_mm2": 0.205},
    "AWG26": {"直径_mm": 0.405, "截面积_mm2": 0.129},
    "AWG28": {"直径_mm": 0.321, "截面积_mm2": 0.081},
    "AWG30": {"直径_mm": 0.255, "截面积_mm2": 0.051},
    "AWG32": {"直径_mm": 0.202, "截面积_mm2": 0.032},
}

# 槽形类型
SLOT_TYPES = {
    "开口槽": {"描述": "开口矩形槽，适用于大功率电机", "Carter系数": 1.2},
    "半开口槽": {"描述": "半开口槽，平衡性能", "Carter系数": 1.1},
    "半闭口槽": {"描述": "半闭口槽，降低齿槽转矩", "Carter系数": 1.05},
    "闭口槽": {"描述": "闭口槽，最小齿槽转矩", "Carter系数": 1.02},
    "无槽": {"描述": "无槽设计（无铁芯）", "Carter系数": 1.0},
}


# ==========================================
# 数据结构类
# ==========================================
@dataclass
class MotorGeometry:
    """电机几何参数"""
    D_out: float        # 外径 (m)
    D_in: float         # 内径 (m)
    h_mag: float        # 永磁体厚度 (m)
    h_coil: float       # 定子盘厚度 (m)
    g_side: float       # 单侧机械气隙 (m)
    
    @property
    def D_avg(self) -> float:
        """平均直径"""
        return (self.D_out + self.D_in) / 2
    
    @property
    def L_eff(self) -> float:
        """有效长度（径向）"""
        return (self.D_out - self.D_in) / 2
    
    @property
    def g_eff(self) -> float:
        """有效气隙"""
        return self.h_coil + 2 * self.g_side
    
    @property
    def active_area(self) -> float:
        """有效面积"""
        return PI * (self.D_out**2 - self.D_in**2) / 4


@dataclass
class StatorGeometry:
    """定子几何参数"""
    D_stator_out: float     # 定子外径 (m)
    D_stator_in: float      # 定子内径 (m)
    h_stator: float         # 定子厚度/叠厚 (m)
    h_yoke: float           # 定子轭部高度 (m)
    slots: int              # 槽数
    slot_type: str          # 槽形类型
    
    @property
    def slot_pitch(self) -> float:
        """槽距"""
        return PI * (self.D_stator_out + self.D_stator_in) / 2 / self.slots


@dataclass
class SlotGeometry:
    """槽形尺寸参数"""
    h_slot: float           # 槽深 (m)
    w_slot_top: float       # 槽口宽度 (m)
    w_slot_bottom: float    # 槽底宽度 (m)
    h_slot_opening: float   # 槽口高度 (m)
    w_slot_opening: float   # 槽口开口宽度 (m)
    h_wedge: float          # 槽楔高度 (m)
    
    @property
    def slot_area(self) -> float:
        """槽面积（近似梯形）"""
        return (self.w_slot_top + self.w_slot_bottom) / 2 * self.h_slot


@dataclass
class MagnetGeometry:
    """永磁体几何参数"""
    h_magnet: float         # 永磁体厚度（充磁方向）(m)
    w_magnet: float         # 永磁体宽度（周向）(m)
    L_magnet: float         # 永磁体长度（径向/轴向）(m)
    magnet_type: str        # 永磁体类型（表贴/内置）
    magnetization: str      # 充磁方式（径向/平行/Halbach）
    
    @property
    def magnet_volume(self) -> float:
        """单块永磁体体积"""
        return self.h_magnet * self.w_magnet * self.L_magnet


@dataclass
class MagneticCircuit:
    """磁路计算结果"""
    Bg_peak: float      # 峰值气隙磁密 (T)
    Bg_avg: float       # 平均磁密 (T)
    Bg_rms: float       # 均方根磁密 (T)
    Phi_pole: float     # 每极磁通 (Wb)
    PC: float           # 磁导系数
    R_gap: float        # 气隙磁阻 (A/Wb)
    R_mag: float        # 永磁体磁阻 (A/Wb)
    Fm: float           # 永磁体磁动势 (A)


@dataclass
class ElectricalParams:
    """电气参数结果"""
    R_phase: float      # 相电阻 (Ω)
    R_line: float       # 线电阻 (Ω)
    L_phase: float      # 相电感 (H)
    L_line: float       # 线电感 (H)
    M_mutual: float     # 互感 (H)
    E_phase_rms: float  # 相反电势有效值 (V)
    E_line_rms: float   # 线反电势有效值 (V)
    Ke: float           # 反电势常数 (V/krpm)
    Kt: float           # 转矩常数 (Nm/A)


@dataclass
class PerformanceMetrics:
    """性能计算结果"""
    T_rated: float      # 额定转矩 (Nm)
    T_avg: float        # 平均转矩 (Nm)
    T_ripple: float     # 转矩脉动 (%)
    T_cogging_peak: float  # 峰值齿槽转矩 (Nm)
    I_phase_rms: float  # 相电流有效值 (A)
    I_line_rms: float   # 线电流有效值 (A)
    J_current: float    # 电流密度 (A/mm²)
    P_out: float        # 输出功率 (W)
    P_in: float         # 输入功率 (W)
    P_cu: float         # 铜损 (W)
    P_eddy: float       # 涡流损耗 (W)
    P_mech: float       # 机械损耗 (W)
    P_core: float       # 铁损 (W)
    Efficiency: float   # 效率 (%)
    V_required: float   # 所需电压 (V)
    V_margin: float     # 电压裕量 (%)
    K_fill: float       # 填充系数


@dataclass
class CalculationResults:
    """完整计算结果容器"""
    geometry: MotorGeometry
    stator_geo: StatorGeometry
    slot_geo: SlotGeometry
    magnet_geo: MagnetGeometry
    magnetic: MagneticCircuit
    electrical: ElectricalParams
    performance: PerformanceMetrics
    waveforms: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典用于导出"""
        return {
            "基本几何参数": asdict(self.geometry),
            "定子几何参数": asdict(self.stator_geo),
            "槽形几何参数": asdict(self.slot_geo),
            "永磁体几何参数": asdict(self.magnet_geo),
            "磁路计算结果": asdict(self.magnetic),
            "电气参数": asdict(self.electrical),
            "性能指标": asdict(self.performance),
            "元数据": self.metadata
        }


# ==========================================
# 核心计算引擎
# ==========================================
class PMDCMotorModel:
    """
    永磁直流电机电磁模型
    
    该类封装了 PMDC/BLDC 电机的所有电磁计算,
    重点支持轴向磁通永磁（AFPM）配置。
    """
    
    def __init__(self, params: Dict):
        """
        使用设计参数初始化电机模型
        
        参数:
        -----------
        params : dict
            包含所有电机设计参数的字典
        """
        self.params = params
        self.results: Optional[CalculationResults] = None
        self._validate_inputs()
        
    def _validate_inputs(self):
        """验证输入参数的物理合理性"""
        p = self.params
        
        # 几何约束
        if p.get("D_out", 0) <= p.get("D_in", 0):
            raise ValueError("外径必须大于内径")
        
        if p.get("D_in", 0) <= 0:
            raise ValueError("内径必须为正值")
            
        if p.get("h_mag", 0) <= 0:
            raise ValueError("永磁体厚度必须为正值")
            
        if p.get("p", 0) < 1:
            raise ValueError("极对数必须至少为1")
            
        # 磁路约束
        if not (0 < p.get("alpha_p", 0) <= 1):
            raise ValueError("极弧系数必须在0到1之间")
            
        if p.get("Br", 0) <= 0:
            raise ValueError("剩磁必须为正值")
    
    def calculate_magnetic_circuit(self) -> MagneticCircuit:
        """
        计算磁路参数
        
        使用磁阻网络分析返回气隙磁密分布及相关参数
        """
        p = self.params
        
        # 提取参数
        D_o = p["D_out"] * 1e-3  # 转换为米
        D_i = p["D_in"] * 1e-3
        h_m = p["h_mag"] * 1e-3
        h_c = p["h_coil"] * 1e-3
        g_s = p["g_side"] * 1e-3
        
        poles = int(p["p"])
        Br = p["Br"]
        alpha_p = p["alpha_p"]
        sigma_m = p.get("sigma_m", 1.15)  # 漏磁系数
        mu_r_mag = p.get("mu_r_mag", 1.05)  # 永磁体相对磁导率
        
        # 有效气隙（对于无铁芯设计包括定子厚度）
        g_eff = h_c + 2 * g_s
        
        # 平均直径和有效长度
        D_avg = (D_o + D_i) / 2
        L_eff = (D_o - D_i) / 2
        
        # 极面积计算
        # 对于AFPM: A_pole = (π/2p) * (R_o² - R_i²) * α_p
        A_pole = (PI / (2 * poles)) * ((D_o/2)**2 - (D_i/2)**2) * alpha_p
        
        # Carter系数（无槽设计约为1）
        slot_type = p.get("slot_type", "无槽")
        k_c = SLOT_TYPES.get(slot_type, {}).get("Carter系数", 1.0)
        
        # 磁阻计算
        # 气隙磁阻
        R_gap = (g_eff * k_c) / (MU0 * A_pole)
        
        # 永磁体磁阻（考虑双转子两侧）
        R_mag = (2 * h_m) / (MU0 * mu_r_mag * A_pole)
        
        # 永磁体磁动势源
        Fm = 2 * (Br / MU0) * h_m / mu_r_mag
        
        # 每极磁通（考虑漏磁）
        Phi_pole = Fm / (R_gap + sigma_m * R_mag)
        
        # 气隙峰值磁密
        Bg_peak = Phi_pole / A_pole
        
        # 对于梯形分布，计算平均值和均方根值
        # 假设准方波，极弧系数影响
        Bg_avg = Bg_peak * alpha_p
        Bg_rms = Bg_peak * math.sqrt(alpha_p)
        
        # 磁导系数（B-H曲线工作点）
        PC = (h_m * 2) / (g_eff * sigma_m)
        
        return MagneticCircuit(
            Bg_peak=Bg_peak,
            Bg_avg=Bg_avg,
            Bg_rms=Bg_rms,
            Phi_pole=Phi_pole,
            PC=PC,
            R_gap=R_gap,
            R_mag=R_mag,
            Fm=Fm
        )
    
    def calculate_electrical_params(self, magnetic: MagneticCircuit) -> ElectricalParams:
        """
        计算电气参数，包括电阻、电感和电动势常数
        """
        p = self.params
        
        # 提取参数
        D_o = p["D_out"] * 1e-3
        D_i = p["D_in"] * 1e-3
        h_c = p["h_coil"] * 1e-3
        g_s = p["g_side"] * 1e-3
        
        poles = int(p["p"])
        N_ph = int(p["N_ph_turns"])
        d_wire = p["d_wire"] * 1e-3
        n_par = int(p["n_parallel"])
        k_w = p["k_w"]
        Temp = p["Temp_coil"]
        n_rated = p["n_rated"]
        waveform = p.get("waveform", "正弦波")
        
        D_avg = (D_o + D_i) / 2
        L_eff = (D_o - D_i) / 2
        
        # 电角频率
        f_el = n_rated * poles / 60
        omega_e = 2 * PI * f_el
        
        # --- 反电动势计算 ---
        # 正弦波: E_ph = 4.44 * f * N * Φ * k_w
        # 梯形波: E_ph = 4 * f * N * Φ * k_w
        if waveform == "正弦波":
            E_ph_rms = 4.44 * f_el * N_ph * magnetic.Phi_pole * k_w
        else:  # 梯形波
            E_ph_rms = 4.0 * f_el * N_ph * magnetic.Phi_pole * k_w
        
        E_line_rms = math.sqrt(3) * E_ph_rms
        
        # 反电势常数 (V/krpm，线电压)
        Ke = E_line_rms / (n_rated / 1000)
        
        # --- 转矩常数 ---
        # Kt = 3 * E_ph / ω_m（三相BLDC）
        omega_m = n_rated * 2 * PI / 60
        Kt = (3 * E_ph_rms) / (math.sqrt(2) * omega_m)  # Nm/A_peak
        Kt_rms = Kt * math.sqrt(2)  # Nm/A_rms
        
        # --- 电阻计算 ---
        # 极距
        tau_p = PI * D_avg / (2 * poles)
        
        # 平均匝长估算
        # 盘式电机端部绕组长度近似
        L_end = tau_p * 1.3  # 端部绕组系数
        L_turn = 2 * L_eff + 2 * L_end
        
        # 每相导体总长度
        L_total = L_turn * N_ph
        
        # 铜导线截面积
        A_cu = PI * (d_wire / 2)**2 * n_par
        
        # 温度修正电阻率
        rho = RHO_CU_20 * (1 + RHO_CU_TEMP_COEFF * (Temp - 20))
        
        # 相电阻和线电阻
        R_phase = rho * L_total / A_cu
        R_line = 2 * R_phase  # Y接法
        
        # --- 电感计算 ---
        # 气隙电感（无铁芯设计中占主导）
        # L_gap = μ0 * N² * A / g_eff
        g_eff = h_c + 2 * g_s
        A_coil = PI * ((D_o/2)**2 - (D_i/2)**2) / 6  # 每相有效面积
        
        L_gap = MU0 * N_ph**2 * A_coil / g_eff
        
        # 端部绕组电感（经验值）
        L_end_ind = 0.15 * L_gap  # 通常为气隙电感的10-20%
        
        # 相电感总值
        L_phase = L_gap + L_end_ind
        
        # 三相互感（平衡时通常为 -0.5 * L_self）
        M_mutual = -0.5 * L_phase * 0.3  # AFPM中耦合降低
        
        # 线电感
        L_line = L_phase - M_mutual
        
        return ElectricalParams(
            R_phase=R_phase,
            R_line=R_line,
            L_phase=L_phase,
            L_line=L_line,
            M_mutual=M_mutual,
            E_phase_rms=E_ph_rms,
            E_line_rms=E_line_rms,
            Ke=Ke,
            Kt=Kt_rms
        )
    
    def calculate_losses(self, electrical: ElectricalParams, I_rms: float) -> Tuple[float, float, float, float]:
        """
        计算电机损耗，包括铜损、涡流损耗、铁损和机械损耗
        """
        p = self.params
        
        D_o = p["D_out"] * 1e-3
        D_i = p["D_in"] * 1e-3
        d_wire = p["d_wire"] * 1e-3
        n_par = int(p["n_parallel"])
        N_ph = int(p["N_ph_turns"])
        n_rated = p["n_rated"]
        poles = int(p["p"])
        Temp = p["Temp_coil"]
        
        f_el = n_rated * poles / 60
        
        # --- 铜损 ---
        P_cu = 3 * I_rms**2 * electrical.R_phase
        
        # --- 涡流损耗 ---
        # 导体中的邻近效应
        # P_eddy ≈ (π²/6) * (f * B * d)² / ρ * V_cu
        rho = RHO_CU_20 * (1 + RHO_CU_TEMP_COEFF * (Temp - 20))
        
        # 估算导体所受磁密
        Bg_local = p.get("Bg_peak", 0.5)  # 将被更新
        
        # 铜体积
        D_avg = (D_o + D_i) / 2
        tau_p = PI * D_avg / (2 * poles)
        L_eff = (D_o - D_i) / 2
        L_turn = 2 * L_eff + 2 * tau_p * 1.3
        A_cu = PI * (d_wire / 2)**2 * n_par
        V_cu = 3 * N_ph * L_turn * A_cu
        
        # 考虑集肤效应的涡流损耗
        delta = math.sqrt(2 * rho / (MU0 * 2 * PI * f_el))  # 趋肤深度
        k_skin = 1.0 if d_wire < 2 * delta else (d_wire / (2 * delta))
        
        P_eddy = (PI**2 / 24) * (f_el * Bg_local * d_wire)**2 / rho * V_cu * k_skin
        
        # --- 铁损 ---
        # 无铁芯设计时铁损很小（仅背铁部分存在）
        P_core = 0.01 * p["P_rated"]  # 估算值
        
        # --- 机械损耗 ---
        # 盘式转子风阻损耗
        omega = n_rated * 2 * PI / 60
        Cm = 0.005  # 封闭盘式转矩系数
        P_windage = 0.5 * Cm * AIR_DENSITY * omega**3 * ((D_o/2)**5 - (D_i/2)**5) * 2
        
        # 轴承摩擦（经验值）
        P_bearing = 0.005 * p["P_rated"] * (n_rated / 3000)
        
        P_mech = P_windage + P_bearing
        
        return P_cu, P_eddy, P_core, P_mech
    
    def calculate_cogging_torque(self, magnetic: MagneticCircuit) -> Tuple[np.ndarray, np.ndarray]:
        """
        使用简化解析方法估算齿槽转矩
        
        对于无槽/无铁芯设计，齿槽转矩很小。
        此方法为有槽定子设计提供估算。
        """
        p = self.params
        
        poles = int(p["p"]) * 2  # 总极数
        slots = int(p.get("slots", poles * 3))  # 默认: 每极3槽
        
        # 最小公倍数决定每转齿槽转矩周期数
        from math import gcd
        lcm = (poles * slots) // gcd(poles, slots)
        
        # 齿槽转矩角度位置
        theta = np.linspace(0, 2*PI, 360)
        
        # 无铁芯设计时齿槽转矩基本为零
        if p.get("coreless", True):
            T_cog = np.zeros_like(theta)
            return theta, T_cog
        
        # 有槽定子的简化齿槽转矩模型
        # T_cog = T_cog_max * sin(lcm * θ)
        
        # 估算峰值齿槽转矩（通常为额定转矩的1-5%）
        T_rated = 9.55 * p["P_rated"] / p["n_rated"]
        k_cog = p.get("k_cogging", 0.02)  # 齿槽系数
        T_cog_peak = k_cog * T_rated
        
        # 包含前几次谐波
        T_cog = T_cog_peak * (np.sin(lcm * theta) + 
                              0.3 * np.sin(2 * lcm * theta) +
                              0.1 * np.sin(3 * lcm * theta))
        
        return theta, T_cog
    
    def calculate_back_emf_waveform(self, magnetic: MagneticCircuit) -> Dict:
        """
        生成反电动势波形用于分析和可视化
        """
        p = self.params
        
        poles = int(p["p"])
        n_rated = p["n_rated"]
        N_ph = int(p["N_ph_turns"])
        k_w = p["k_w"]
        alpha_p = p["alpha_p"]
        waveform = p.get("waveform", "正弦波")
        
        # 时间和角度数组
        f_el = n_rated * poles / 60
        T_period = 1 / f_el
        t = np.linspace(0, 2 * T_period, 720)
        theta_e = 2 * PI * f_el * t  # 电角度
        theta_m = theta_e / poles     # 机械角度
        
        # 峰值电动势计算
        omega_e = 2 * PI * f_el
        E_peak = omega_e * N_ph * magnetic.Phi_pole * k_w
        
        if waveform == "正弦波":
            # 正弦反电动势
            E_a = E_peak * np.sin(theta_e)
            E_b = E_peak * np.sin(theta_e - 2*PI/3)
            E_c = E_peak * np.sin(theta_e - 4*PI/3)
        else:
            # 梯形反电动势
            E_a = self._trapezoidal_emf(theta_e, E_peak, alpha_p)
            E_b = self._trapezoidal_emf(theta_e - 2*PI/3, E_peak, alpha_p)
            E_c = self._trapezoidal_emf(theta_e - 4*PI/3, E_peak, alpha_p)
        
        # 线电压反电动势
        E_ab = E_a - E_b
        E_bc = E_b - E_c
        E_ca = E_c - E_a
        
        # 理想正弦参考
        E_ideal = E_peak * np.sin(theta_e)
        
        return {
            "time": t,
            "theta_e": theta_e,
            "theta_m": np.degrees(theta_m),
            "E_a": E_a,
            "E_b": E_b,
            "E_c": E_c,
            "E_ab": E_ab,
            "E_bc": E_bc,
            "E_ca": E_ca,
            "E_ideal": E_ideal,
            "E_peak": E_peak,
            "E_rms": E_peak / math.sqrt(2)
        }
    
    def _trapezoidal_emf(self, theta: np.ndarray, E_peak: float, alpha_p: float) -> np.ndarray:
        """生成梯形反电动势波形"""
        theta = np.mod(theta, 2*PI)
        E = np.zeros_like(theta)
        
        # 平顶持续时间（弧度）
        flat_angle = PI * alpha_p
        rise_angle = PI * (1 - alpha_p) / 2
        
        for i, th in enumerate(theta):
            th_mod = th % (2*PI)
            if th_mod < rise_angle:
                E[i] = E_peak * th_mod / rise_angle
            elif th_mod < rise_angle + flat_angle:
                E[i] = E_peak
            elif th_mod < PI:
                E[i] = E_peak * (PI - th_mod) / rise_angle
            elif th_mod < PI + rise_angle:
                E[i] = -E_peak * (th_mod - PI) / rise_angle
            elif th_mod < PI + rise_angle + flat_angle:
                E[i] = -E_peak
            else:
                E[i] = -E_peak * (2*PI - th_mod) / rise_angle
        
        return E
    
    def calculate_torque_waveform(self, electrical: ElectricalParams) -> Dict:
        """
        计算瞬时转矩波形，包括脉动
        """
        p = self.params
        
        poles = int(p["p"])
        n_rated = p["n_rated"]
        P_out = p["P_rated"]
        
        # 额定转矩
        T_rated = 9.55 * P_out / n_rated
        
        # 电角度
        theta_e = np.linspace(0, 4*PI, 720)  # 两个电周期
        
        # 平均转矩
        T_avg = T_rated
        
        # 转矩脉动分量（简化模型）
        # 三相BLDC以6次谐波为主
        k_6 = p.get("k_ripple_6", 0.05)  # 5% 六次谐波
        k_12 = p.get("k_ripple_12", 0.02)  # 2% 十二次谐波
        
        T_ripple = k_6 * np.cos(6 * theta_e) + k_12 * np.cos(12 * theta_e)
        
        T_inst = T_avg * (1 + T_ripple)
        
        # 转矩脉动百分比
        T_ripple_pct = (np.max(T_inst) - np.min(T_inst)) / T_avg * 100
        
        return {
            "theta_e": np.degrees(theta_e),
            "T_inst": T_inst,
            "T_avg": T_avg,
            "T_ripple_pct": T_ripple_pct,
            "T_max": np.max(T_inst),
            "T_min": np.min(T_inst)
        }
    
    def calculate_flux_distribution(self, magnetic: MagneticCircuit) -> Dict:
        """
        计算气隙磁密分布（相对于机械角度）
        """
        p = self.params
        
        poles = int(p["p"]) * 2
        alpha_p = p["alpha_p"]
        
        # 机械角度（一圈）
        theta_m = np.linspace(0, 360, 720)
        theta_m_rad = np.radians(theta_m)
        
        # 极距（度）
        pole_pitch = 360 / poles
        
        # 生成准方波磁密分布
        Bg = np.zeros_like(theta_m)
        
        for i, th in enumerate(theta_m):
            # 极对内的位置
            th_pole = th % (2 * pole_pitch)
            
            if th_pole < pole_pitch * alpha_p:
                Bg[i] = magnetic.Bg_peak
            elif th_pole < pole_pitch:
                Bg[i] = 0
            elif th_pole < pole_pitch * (1 + alpha_p):
                Bg[i] = -magnetic.Bg_peak
            else:
                Bg[i] = 0
        
        # 计算统计值
        Bg_avg = np.mean(np.abs(Bg))
        Bg_rms = np.sqrt(np.mean(Bg**2))
        
        # FFT分析
        Bg_fft = np.fft.fft(Bg)
        freqs = np.fft.fftfreq(len(Bg), 1/720)
        Bg_spectrum = np.abs(Bg_fft[:len(Bg)//2]) / len(Bg) * 2
        harmonics = np.arange(len(Bg_spectrum)) * poles / 2
        
        return {
            "theta_m": theta_m,
            "Bg": Bg,
            "Bg_peak": magnetic.Bg_peak,
            "Bg_avg": Bg_avg,
            "Bg_rms": Bg_rms,
            "harmonics": harmonics[:50],
            "spectrum": Bg_spectrum[:50]
        }
    
    def run_full_analysis(self) -> CalculationResults:
        """
        执行完整的电磁分析
        """
        p = self.params
        
        # 创建几何对象
        geometry = MotorGeometry(
            D_out=p["D_out"] * 1e-3,
            D_in=p["D_in"] * 1e-3,
            h_mag=p["h_mag"] * 1e-3,
            h_coil=p["h_coil"] * 1e-3,
            g_side=p["g_side"] * 1e-3
        )
        
        # 创建定子几何对象
        stator_geo = StatorGeometry(
            D_stator_out=p.get("D_stator_out", p["D_out"]) * 1e-3,
            D_stator_in=p.get("D_stator_in", p["D_in"]) * 1e-3,
            h_stator=p.get("h_stator", p["h_coil"]) * 1e-3,
            h_yoke=p.get("h_yoke", 5.0) * 1e-3,
            slots=int(p.get("slots", int(p["p"]) * 6)),
            slot_type=p.get("slot_type", "无槽")
        )
        
        # 创建槽形几何对象
        slot_geo = SlotGeometry(
            h_slot=p.get("h_slot", 15.0) * 1e-3,
            w_slot_top=p.get("w_slot_top", 8.0) * 1e-3,
            w_slot_bottom=p.get("w_slot_bottom", 6.0) * 1e-3,
            h_slot_opening=p.get("h_slot_opening", 1.0) * 1e-3,
            w_slot_opening=p.get("w_slot_opening", 3.0) * 1e-3,
            h_wedge=p.get("h_wedge", 2.0) * 1e-3
        )
        
        # 创建永磁体几何对象
        magnet_geo = MagnetGeometry(
            h_magnet=p.get("h_mag", 5.0) * 1e-3,
            w_magnet=p.get("w_magnet", 20.0) * 1e-3,
            L_magnet=p.get("L_magnet", 30.0) * 1e-3,
            magnet_type=p.get("magnet_type", "表贴式"),
            magnetization=p.get("magnetization", "径向充磁")
        )
        
        # 磁路分析
        magnetic = self.calculate_magnetic_circuit()
        
        # 更新Bg_peak用于损耗计算
        p["Bg_peak"] = magnetic.Bg_peak
        
        # 电气参数
        electrical = self.calculate_electrical_params(magnetic)
        
        # 计算额定电流
        T_rated = 9.55 * p["P_rated"] / p["n_rated"]
        I_rms = T_rated / electrical.Kt
        
        # 计算损耗
        P_cu, P_eddy, P_core, P_mech = self.calculate_losses(electrical, I_rms)
        
        # 总损耗和效率
        P_loss = P_cu + P_eddy + P_core + P_mech
        P_in = p["P_rated"] + P_loss
        Efficiency = p["P_rated"] / P_in * 100
        
        # 电压需求
        V_res = I_rms * electrical.R_line
        V_ind = 2 * PI * (p["n_rated"] * int(p["p"]) / 60) * electrical.L_line * I_rms
        V_req = math.sqrt(electrical.E_line_rms**2 + V_res**2 + V_ind**2) * 1.05
        V_margin = (p["V_dc"] - V_req) / p["V_dc"] * 100
        
        # 填充系数计算
        D_o, D_i = p["D_out"] * 1e-3, p["D_in"] * 1e-3
        d_wire = p["d_wire"] * 1e-3
        n_par = int(p["n_parallel"])
        N_ph = int(p["N_ph_turns"])
        
        # 内径填充系数（关键约束）
        K_fill = (3 * N_ph * 2 * n_par * d_wire) / (PI * D_i)
        
        # 电流密度
        A_cu = PI * (d_wire / 2)**2 * n_par
        J = I_rms / (A_cu * 1e6)  # A/mm²
        
        # 转矩分析
        torque_data = self.calculate_torque_waveform(electrical)
        theta_cog, T_cog = self.calculate_cogging_torque(magnetic)
        
        # 性能指标
        performance = PerformanceMetrics(
            T_rated=T_rated,
            T_avg=torque_data["T_avg"],
            T_ripple=torque_data["T_ripple_pct"],
            T_cogging_peak=np.max(np.abs(T_cog)),
            I_phase_rms=I_rms,
            I_line_rms=I_rms,  # Y接法相同
            J_current=J,
            P_out=p["P_rated"],
            P_in=P_in,
            P_cu=P_cu,
            P_eddy=P_eddy,
            P_mech=P_mech,
            P_core=P_core,
            Efficiency=Efficiency,
            V_required=V_req,
            V_margin=V_margin,
            K_fill=K_fill
        )
        
        # 波形数据
        waveforms = {
            "back_emf": self.calculate_back_emf_waveform(magnetic),
            "torque": torque_data,
            "flux": self.calculate_flux_distribution(magnetic),
            "cogging": {"theta": theta_cog, "T_cog": T_cog}
        }
        
        # 元数据
        metadata = {
            "计算时间": datetime.now().isoformat(),
            "模型版本": "6.0",
            "波形类型": p.get("waveform", "正弦波")
        }
        
        self.results = CalculationResults(
            geometry=geometry,
            stator_geo=stator_geo,
            slot_geo=slot_geo,
            magnet_geo=magnet_geo,
            magnetic=magnetic,
            electrical=electrical,
            performance=performance,
            waveforms=waveforms,
            metadata=metadata
        )
        
        return self.results


# ==========================================
# 图形用户界面应用
# ==========================================
class ScrollableFrame(ttk.Frame):
    """可滚动容器组件"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind("<Configure>", 
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.canvas_window = self.canvas.create_window((0, 0), 
            window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # 鼠标滚轮绑定
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")


class MotorCalculatorApp:
    """
    轴向磁通永磁电机设计与分析应用程序
    
    主应用类，提供电机电磁分析的图形界面
    包含全面的可视化和数据导出功能
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("永磁直流/无刷直流电机电磁分析工具 v6.0")
        self.root.geometry("1800x1000")
        
        # 配置样式
        self._setup_styles()
        
        # 主布局
        main_layout = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main_layout.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧面板 - 输入参数
        left_panel = ttk.LabelFrame(main_layout, text="设计参数")
        main_layout.add(left_panel, weight=1)
        
        self.input_frame = ScrollableFrame(left_panel)
        self.input_frame.pack(fill=tk.BOTH, expand=True)
        
        # 右侧面板 - 结果
        right_panel = ttk.LabelFrame(main_layout, text="分析结果")
        main_layout.add(right_panel, weight=3)
        
        # 选项卡
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建各选项卡
        self._create_report_tab()
        self._create_curves_tab()
        self._create_emf_tab()
        self._create_torque_tab()
        self._create_flux_tab()
        self._create_geometry_tab()
        
        # 创建输入字段
        self.entries = {}
        self.vars = {}
        self._create_inputs()
        
        # 按钮面板
        self._create_buttons(left_panel)
        
        # 存储计算结果
        self.calc_results: Optional[CalculationResults] = None
        self.calculation_history = []
        self.generated_figures = {}
        
    def _setup_styles(self):
        """配置ttk样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Header.TLabel", 
                       font=("微软雅黑", 11, "bold"), 
                       foreground="#003366")
        style.configure("SubHeader.TLabel", 
                       font=("微软雅黑", 10, "bold"), 
                       foreground="#004488")
        style.configure("Warning.TLabel",
                       font=("微软雅黑", 10),
                       foreground="#CC0000")
        style.configure("Success.TLabel",
                       font=("微软雅黑", 10),
                       foreground="#006600")
        style.configure("Action.TButton",
                       font=("微软雅黑", 10, "bold"))
        
    def _clear_tab(self, tab):
        for widget in tab.winfo_children():
            widget.destroy()

    def _set_chart_placeholder(self, tab, title: str, message: str):
        self._clear_tab(tab)
        container = ttk.Frame(tab, padding=24)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(container, text=title, style="Header.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(
            container,
            text=message,
            style="Warning.TLabel",
            justify=tk.LEFT,
            wraplength=760,
        ).pack(anchor="w")

    def _register_figure(self, key: str, figure):
        self.generated_figures[key] = figure

    def _clear_figure(self, key: str):
        self.generated_figures.pop(key, None)

    def _create_report_tab(self):
        """创建详细报告选项卡"""
        self.report_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.report_tab, text="📋 详细报告")
        
        # 工具栏
        toolbar = ttk.Frame(self.report_tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="📋 复制", 
                  command=self._copy_report).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 保存报告", 
                  command=self._save_report).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📄 导出TXT", 
                  command=self._export_txt).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🖨 打印预览", 
                  command=self._print_report).pack(side=tk.LEFT, padx=2)
        
        self.result_text = scrolledtext.ScrolledText(
            self.report_tab, 
            width=80, 
            height=45, 
            font=("Consolas", 10),
            wrap=tk.WORD
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def _create_curves_tab(self):
        """创建性能曲线选项卡"""
        self.curves_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.curves_tab, text="📈 性能曲线")
        
    def _create_emf_tab(self):
        """创建反电动势波形选项卡"""
        self.emf_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.emf_tab, text="⚡ 反电动势")
        
    def _create_torque_tab(self):
        """创建转矩分析选项卡"""
        self.torque_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.torque_tab, text="🔧 转矩分析")
        
    def _create_flux_tab(self):
        """创建磁密分布选项卡"""
        self.flux_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.flux_tab, text="🧲 磁密分布")
        
    def _create_geometry_tab(self):
        """创建几何可视化选项卡"""
        self.geo_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.geo_tab, text="📐 几何结构")
        
    def _create_inputs(self):
        """创建所有输入参数字段"""
        f = self.input_frame.scrollable_frame
        row = 0
        
        def add_header(text: str):
            nonlocal row
            ttk.Label(f, text=text, style="Header.TLabel").grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(15, 5), padx=5)
            row += 1
            
        def add_subheader(text: str):
            nonlocal row
            ttk.Label(f, text=text, style="SubHeader.TLabel").grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(8, 3), padx=10)
            row += 1
            
        def add_field(key: str, label: str, default, unit: str, tooltip: str = ""):
            nonlocal row
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=5)
            var = tk.StringVar(value=str(default))
            entry = ttk.Entry(f, width=12, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", padx=5)
            ttk.Label(f, text=unit).grid(row=row, column=2, sticky="w", padx=5)
            self.entries[key] = entry
            self.vars[key] = var
            row += 1
            
        def add_combo(key: str, label: str, values: list, default: str):
            nonlocal row
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=5)
            var = tk.StringVar(value=default)
            combo = ttk.Combobox(f, textvariable=var, values=values, width=10, state="readonly")
            combo.grid(row=row, column=1, sticky="ew", padx=5)
            self.vars[key] = var
            row += 1
            return combo
        
        f.columnconfigure(1, weight=1)
        
        # 1. 运行规格
        add_header("一、运行规格参数")
        add_field("V_dc", "直流母线电压", 48.0, "V")
        add_field("P_rated", "额定输出功率", 800.0, "W")
        add_field("n_rated", "额定转速", 2500.0, "rpm")
        add_field("Temp_coil", "绕组温度", 80.0, "°C")
        
        # 2. 基本几何尺寸
        add_header("二、电机基本尺寸")
        add_field("D_out", "电机外径", 140.0, "mm")
        add_field("D_in", "电机内径", 70.0, "mm")
        add_field("g_side", "机械气隙（单侧）", 1.0, "mm")
        
        # 3. 定子尺寸（新增）
        add_header("三、定子尺寸参数")
        add_field("D_stator_out", "定子外径", 138.0, "mm")
        add_field("D_stator_in", "定子内径", 72.0, "mm")
        add_field("h_stator", "定子叠厚/厚度", 20.0, "mm")
        add_field("h_coil", "定子盘厚度", 5.0, "mm")
        add_field("h_yoke", "定子轭部高度", 5.0, "mm")
        add_field("slots", "槽数", 24, "个")
        
        # 槽形类型选择
        self.slot_type_combo = add_combo("slot_type", "槽形类型", 
                                         list(SLOT_TYPES.keys()), "无槽")
        
        # 4. 槽形尺寸（新增）
        add_header("四、槽形尺寸参数")
        add_field("h_slot", "槽深", 15.0, "mm")
        add_field("w_slot_top", "槽口宽度", 8.0, "mm")
        add_field("w_slot_bottom", "槽底宽度", 6.0, "mm")
        add_field("h_slot_opening", "槽口高度", 1.0, "mm")
        add_field("w_slot_opening", "槽口开口宽度", 3.0, "mm")
        add_field("h_wedge", "槽楔高度", 2.0, "mm")
        
        # 5. 永磁体尺寸（新增/扩展）
        add_header("五、永磁体尺寸参数")
        add_field("h_mag", "永磁体厚度（充磁方向）", 5.0, "mm")
        add_field("w_magnet", "永磁体宽度（周向）", 20.0, "mm")
        add_field("L_magnet", "永磁体长度（径向）", 30.0, "mm")
        
        # 永磁体类型选择
        self.magnet_type_combo = add_combo("magnet_type", "永磁体类型", 
                                           ["表贴式", "内置式-V型", "内置式-一字型", "内置式-U型"], "表贴式")
        
        # 充磁方式选择
        self.magnetization_combo = add_combo("magnetization", "充磁方式", 
                                             ["径向充磁", "平行充磁", "Halbach阵列"], "径向充磁")
        
        # 6. 磁路参数
        add_header("六、磁路参数")
        add_field("p", "极对数", 8, "对")
        
        # 永磁体牌号选择
        self.mag_combo = add_combo("magnet_grade", "永磁体牌号", 
                                   list(MAGNET_LIBRARY.keys()), "N42")
        self.mag_combo.bind("<<ComboboxSelected>>", self._on_magnet_select)
        
        add_field("Br", "剩磁", 1.28, "T")
        add_field("alpha_p", "极弧系数", 0.70, "-")
        add_field("sigma_m", "漏磁系数", 1.15, "-")
        add_field("mu_r_mag", "永磁体相对磁导率", 1.05, "-")
        
        # 7. 绕组参数
        add_header("七、绕组参数")
        add_field("N_ph_turns", "每相匝数", 50, "匝")
        add_field("d_wire", "导线直径", 0.9, "mm")
        add_field("n_parallel", "并联根数", 2, "根")
        add_field("k_w", "绕组系数", 0.93, "-")
        add_field("fill_limit", "填充系数限制", 0.65, "-")
        
        # 8. 分析选项
        add_header("八、分析选项")
        self.waveform_combo = add_combo("waveform", "反电势波形", 
                                        ["正弦波", "梯形波"], "正弦波")
        
        add_field("k_cogging", "齿槽转矩系数", 0.02, "-")
        add_field("k_ripple_6", "6次谐波转矩系数", 0.05, "-")
        add_field("k_ripple_12", "12次谐波转矩系数", 0.02, "-")
        
        # 无铁芯选项
        self.coreless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="无铁芯定子设计", 
                       variable=self.coreless_var).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=5)
        row += 1
        
    def _on_magnet_select(self, event=None):
        """选择永磁体牌号时更新剩磁"""
        grade = self.vars["magnet_grade"].get()
        if grade in MAGNET_LIBRARY:
            self.vars["Br"].set(str(MAGNET_LIBRARY[grade]["Br"]))
            
    def _create_buttons(self, parent):
        """创建操作按钮"""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)
        
        ttk.Button(btn_frame, text="🔬 运行分析", 
                  command=self.run_analysis, 
                  style="Action.TButton").pack(fill=tk.X, pady=3)
        
        ttk.Button(btn_frame, text="⚡ 快速优化", 
                  command=self.run_optimization).pack(fill=tk.X, pady=3)
        
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="💾 导出JSON", 
                  command=self.export_json).pack(fill=tk.X, pady=3)
        
        ttk.Button(btn_frame, text="📊 导出CSV", 
                  command=self.export_csv).pack(fill=tk.X, pady=3)
        
        ttk.Button(btn_frame, text="📄 导出TXT完整数据", 
                  command=self._export_full_txt).pack(fill=tk.X, pady=3)
        
        ttk.Button(btn_frame, text="📷 保存图表", 
                  command=self.save_plots).pack(fill=tk.X, pady=3)
        
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="🔄 恢复默认", 
                  command=self.reset_defaults).pack(fill=tk.X, pady=3)
        
    def _get_params(self) -> Dict:
        """收集所有输入字段的参数"""
        params = {}
        for key, var in self.vars.items():
            try:
                val = var.get()
                # 尝试转换为数字
                if '.' in val:
                    params[key] = float(val)
                else:
                    try:
                        params[key] = int(val)
                    except ValueError:
                        params[key] = val
            except:
                params[key] = 0.0
                
        params["coreless"] = self.coreless_var.get()
        return params
    
    def run_analysis(self):
        """执行完整的电磁分析"""
        try:
            params = self._get_params()
            
            # 创建电机模型
            model = PMDCMotorModel(params)
            
            # 运行分析
            self.calc_results = model.run_full_analysis()
            
            # 存储到历史记录
            self.calculation_history.append({
                "timestamp": datetime.now().isoformat(),
                "params": params,
                "results": self.calc_results.to_dict()
            })
            
            # 更新显示
            self._display_report()
            self._plot_performance_curves()
            self._plot_back_emf()
            self._plot_torque()
            self._plot_flux_distribution()
            self._draw_geometry()
            
            # 切换到报告选项卡
            self.notebook.select(0)
            
            messagebox.showinfo("分析完成", "电磁分析计算已完成！\n请查看各选项卡中的结果。")
            
        except Exception as e:
            messagebox.showerror("分析错误", f"计算失败:\n{str(e)}")
            raise
            
    def _display_report(self):
        """生成并显示详细计算报告"""
        r = self.calc_results
        p = self._get_params()
        
        self.result_text.delete(1.0, tk.END)
        
        # 报告头
        report = []
        report.append("=" * 70)
        report.append("   永磁直流/无刷直流电机电磁分析报告")
        report.append("=" * 70)
        report.append(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"   模型版本: {r.metadata.get('模型版本', 'N/A')}")
        report.append("=" * 70)
        report.append("")
        
        # 设计验证
        warnings = self._check_design_validity(r)
        if warnings:
            report.append(">>> 设计可行性检查 <<<")
            report.append("-" * 50)
            for w in warnings:
                report.append(f"  {w}")
            report.append("-" * 50)
            report.append("")
        
        # 1. 输入参数汇总
        report.append("一、输入参数汇总")
        report.append("-" * 50)
        report.append(f"   直流母线电压      : {p['V_dc']:.1f} V")
        report.append(f"   额定功率          : {p['P_rated']:.1f} W")
        report.append(f"   额定转速          : {p['n_rated']:.0f} rpm")
        report.append(f"   极对数            : {p['p']}")
        report.append(f"   电机外径          : {p['D_out']:.1f} mm")
        report.append(f"   电机内径          : {p['D_in']:.1f} mm")
        report.append(f"   每相匝数          : {p['N_ph_turns']}")
        report.append("")
        
        # 2. 定子几何参数
        report.append("二、定子几何参数")
        report.append("-" * 50)
        report.append(f"   定子外径          : {p.get('D_stator_out', p['D_out']):.1f} mm")
        report.append(f"   定子内径          : {p.get('D_stator_in', p['D_in']):.1f} mm")
        report.append(f"   定子叠厚          : {p.get('h_stator', 20.0):.1f} mm")
        report.append(f"   定子盘厚度        : {p.get('h_coil', 5.0):.1f} mm")
        report.append(f"   定子轭部高度      : {p.get('h_yoke', 5.0):.1f} mm")
        report.append(f"   槽数              : {p.get('slots', 24)}")
        report.append(f"   槽形类型          : {p.get('slot_type', '无槽')}")
        report.append("")
        
        # 3. 槽形几何参数
        report.append("三、槽形几何参数")
        report.append("-" * 50)
        report.append(f"   槽深              : {p.get('h_slot', 15.0):.1f} mm")
        report.append(f"   槽口宽度          : {p.get('w_slot_top', 8.0):.1f} mm")
        report.append(f"   槽底宽度          : {p.get('w_slot_bottom', 6.0):.1f} mm")
        report.append(f"   槽口高度          : {p.get('h_slot_opening', 1.0):.1f} mm")
        report.append(f"   槽口开口宽度      : {p.get('w_slot_opening', 3.0):.1f} mm")
        report.append(f"   槽楔高度          : {p.get('h_wedge', 2.0):.1f} mm")
        slot_area = (p.get('w_slot_top', 8.0) + p.get('w_slot_bottom', 6.0)) / 2 * p.get('h_slot', 15.0)
        report.append(f"   槽面积（估算）    : {slot_area:.1f} mm²")
        report.append("")
        
        # 4. 永磁体几何参数
        report.append("四、永磁体几何参数")
        report.append("-" * 50)
        report.append(f"   永磁体厚度        : {p.get('h_mag', 5.0):.1f} mm")
        report.append(f"   永磁体宽度（周向）: {p.get('w_magnet', 20.0):.1f} mm")
        report.append(f"   永磁体长度（径向）: {p.get('L_magnet', 30.0):.1f} mm")
        report.append(f"   永磁体类型        : {p.get('magnet_type', '表贴式')}")
        report.append(f"   充磁方式          : {p.get('magnetization', '径向充磁')}")
        report.append(f"   永磁体牌号        : {p.get('magnet_grade', 'N42')}")
        magnet_vol = p.get('h_mag', 5.0) * p.get('w_magnet', 20.0) * p.get('L_magnet', 30.0)
        report.append(f"   单块永磁体体积    : {magnet_vol:.1f} mm³")
        total_magnets = int(p['p']) * 2
        report.append(f"   永磁体总数        : {total_magnets} 块")
        report.append(f"   永磁体总体积      : {magnet_vol * total_magnets / 1000:.2f} cm³")
        report.append("")
        
        # 5. 磁路计算结果
        m = r.magnetic
        report.append("五、磁路计算结果")
        report.append("-" * 50)
        report.append(f"   峰值气隙磁密 (Bg_peak) : {m.Bg_peak:.4f} T")
        report.append(f"   平均磁密 (Bg_avg)      : {m.Bg_avg:.4f} T")
        report.append(f"   均方根磁密 (Bg_rms)    : {m.Bg_rms:.4f} T")
        report.append(f"   每极磁通 (Φ)           : {m.Phi_pole*1e3:.4f} mWb")
        report.append(f"   磁导系数 (PC)          : {m.PC:.2f}")
        report.append(f"   气隙磁阻               : {m.R_gap/1e6:.2f} MAt/Wb")
        report.append(f"   永磁体磁阻             : {m.R_mag/1e6:.2f} MAt/Wb")
        report.append(f"   永磁体磁动势           : {m.Fm:.1f} A")
        report.append("")
        
        # 6. 电气参数
        e = r.electrical
        report.append("六、电气参数")
        report.append("-" * 50)
        report.append(f"   相电阻 (R_ph)          : {e.R_phase*1e3:.3f} mΩ")
        report.append(f"   线电阻 (R_line)        : {e.R_line*1e3:.3f} mΩ")
        report.append(f"   相电感 (L_ph)          : {e.L_phase*1e6:.2f} µH")
        report.append(f"   线电感 (L_line)        : {e.L_line*1e6:.2f} µH")
        report.append(f"   互感 (M)               : {e.M_mutual*1e6:.2f} µH")
        report.append(f"   相反电势有效值 (E_ph)  : {e.E_phase_rms:.2f} V")
        report.append(f"   线反电势有效值 (E_line): {e.E_line_rms:.2f} V")
        report.append(f"   反电势常数 (Ke)        : {e.Ke:.2f} V/krpm")
        report.append(f"   转矩常数 (Kt)          : {e.Kt:.4f} Nm/A")
        report.append(f"   电气时间常数           : {e.L_phase / e.R_phase * 1e3:.3f} ms")
        report.append("")
        
        # 7. 额定工况性能
        perf = r.performance
        report.append("七、额定工况性能")
        report.append("-" * 50)
        report.append(f"   额定转矩              : {perf.T_rated:.3f} Nm")
        report.append(f"   平均转矩              : {perf.T_avg:.3f} Nm")
        report.append(f"   转矩脉动              : {perf.T_ripple:.2f} %")
        report.append(f"   峰值齿槽转矩          : {perf.T_cogging_peak:.4f} Nm")
        report.append(f"   相电流有效值          : {perf.I_phase_rms:.2f} A")
        report.append(f"   电流密度 (J)          : {perf.J_current:.2f} A/mm²")
        report.append(f"   所需电压              : {perf.V_required:.1f} V")
        report.append(f"   Legacy 直流母线差额   : {perf.V_margin:.1f} %")
        report.append(f"   Legacy 线性绕组占比   : {perf.K_fill:.3f}")
        report.append("")
        
        # 8. 损耗分析
        report.append("八、损耗分析")
        report.append("-" * 50)
        report.append(f"   铜损 (P_cu)           : {perf.P_cu:.1f} W")
        report.append(f"   涡流损耗 (P_eddy)     : {perf.P_eddy:.1f} W")
        report.append(f"   铁损 (P_core)         : {perf.P_core:.1f} W")
        report.append(f"   机械损耗 (P_mech)     : {perf.P_mech:.1f} W")
        total_loss = perf.P_cu + perf.P_eddy + perf.P_core + perf.P_mech
        report.append(f"   总损耗                : {total_loss:.1f} W")
        report.append(f"   输入功率              : {perf.P_in:.1f} W")
        report.append(f"   输出功率              : {perf.P_out:.1f} W")
        report.append(f"   效率                  : {perf.Efficiency:.2f} %")
        report.append("")
        
        # 9. 关键性能指标汇总
        report.append("九、关键性能指标 (KPI)")
        report.append("-" * 50)
        power_density = perf.P_out / (r.geometry.active_area * r.geometry.h_coil * 1e6)
        torque_density = perf.T_rated / (r.geometry.active_area * 1e4)
        report.append(f"   功率密度              : {power_density:.2f} W/cm³")
        report.append(f"   转矩密度              : {torque_density:.3f} Nm/cm²")
        report.append(f"   转矩电流比            : {perf.T_rated / perf.I_phase_rms:.4f} Nm/A")
        report.append(f"   电气时间常数          : {e.L_phase / e.R_phase * 1e3:.3f} ms")
        report.append("")
        
        report.append("=" * 70)
        report.append("                    报告结束")
        report.append("=" * 70)
        
        # 插入到文本框
        self.result_text.insert(tk.END, "\n".join(report))
        self.result_text.see(1.0)
        
    def _check_design_validity(self, r: CalculationResults) -> List[str]:
        """检查设计潜在问题"""
        warnings = []
        perf = r.performance
        
        if perf.J_current > 10:
            warnings.append("⚠️ 严重: 电流密度过高 (>10 A/mm²) - 有热失效风险!")
        elif perf.J_current > 6:
            warnings.append("⚠️ 警告: 电流密度较高 (>6 A/mm²) - 需要强制冷却")
        
        if perf.V_margin < 5:
            warnings.append("⚠️ 警告: 电压裕量不足 (<5%) - 动态响应受限")
        elif perf.V_margin > 40:
            warnings.append("ℹ️ 提示: 电压裕量较大 (>40%) - 考虑增加匝数")
        
        if perf.K_fill > 0.8:
            warnings.append("⚠️ 严重: 填充系数超过实际限制 (>0.8) - 无法制造!")
        elif perf.K_fill > 0.6:
            warnings.append("⚠️ 警告: 填充系数较高 (>0.6) - 制造难度较大")
        
        if perf.Efficiency < 85:
            warnings.append("ℹ️ 提示: 效率低于85% - 建议进行设计优化")
            
        if r.magnetic.Bg_peak > 1.0:
            warnings.append("⚠️ 警告: 气隙磁密较高 - 请验证永磁体工作点")
            
        return warnings
    
    def _plot_performance_curves(self):
        """绘制转速-转矩和效率曲线"""
        self._clear_tab(self.curves_tab)
        self._clear_figure("performance_curves")
            
        if not self.calc_results:
            return

        if not MATPLOTLIB_AVAILABLE:
            self._set_chart_placeholder(
                self.curves_tab,
                "性能曲线不可用",
                "当前环境未安装 matplotlib，仍可进行默认计算和导出 JSON/CSV/TXT，但图表显示与图表保存功能已禁用。",
            )
            return
            
        r = self.calc_results
        p = self._get_params()
        
        fig = Figure(figsize=(12, 8), dpi=100)
        
        # 创建2x2子图网格
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # 生成运行范围数据
        T_max = r.performance.T_rated * 2.5
        torques = np.linspace(0.01, T_max, 100)
        
        speeds = []
        efficiencies = []
        currents = []
        powers_out = []
        
        V_dc = p["V_dc"]
        Ke = r.electrical.Ke
        Kt = r.electrical.Kt
        R_line = r.electrical.R_line
        
        for T in torques:
            I = T / Kt
            V_drop = I * R_line
            E_req = V_dc - V_drop
            n = max(0, E_req / (Ke / 1000))
            
            P_out = T * n * 2 * PI / 60
            P_cu = 3 * I**2 * r.electrical.R_phase
            P_mech = r.performance.P_mech * (n / p["n_rated"])**2 if n > 0 else 0
            P_in = P_out + P_cu + P_mech + r.performance.P_eddy
            
            eff = (P_out / P_in * 100) if P_in > 0 else 0
            
            speeds.append(n)
            efficiencies.append(eff)
            currents.append(I)
            powers_out.append(P_out)
        
        # 图1: 转速-转矩特性
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(torques, speeds, 'b-', linewidth=2, label='转速')
        ax1.axhline(y=p["n_rated"], color='b', linestyle='--', alpha=0.5, label=f'额定: {p["n_rated"]} rpm')
        ax1.axvline(x=r.performance.T_rated, color='r', linestyle='--', alpha=0.5, label=f'额定: {r.performance.T_rated:.2f} Nm')
        ax1.set_xlabel('转矩 (Nm)', fontsize=10)
        ax1.set_ylabel('转速 (rpm)', fontsize=10, color='b')
        ax1.set_title('转速-转矩特性曲线', fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=8)
        ax1.set_xlim(0, T_max)
        ax1.set_ylim(0, None)
        
        # 图2: 效率曲线
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.plot(torques, efficiencies, 'g-', linewidth=2)
        ax2.axhline(y=r.performance.Efficiency, color='g', linestyle='--', alpha=0.5, 
                   label=f'额定: {r.performance.Efficiency:.1f}%')
        ax2.set_xlabel('转矩 (Nm)', fontsize=10)
        ax2.set_ylabel('效率 (%)', fontsize=10, color='g')
        ax2.set_title('效率-转矩曲线', fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='lower right', fontsize=8)
        ax2.set_xlim(0, T_max)
        ax2.set_ylim(0, 100)
        
        # 图3: 电流-转矩曲线
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.plot(torques, currents, 'r-', linewidth=2)
        ax3.axhline(y=r.performance.I_phase_rms, color='r', linestyle='--', alpha=0.5,
                   label=f'额定: {r.performance.I_phase_rms:.1f} A')
        ax3.set_xlabel('转矩 (Nm)', fontsize=10)
        ax3.set_ylabel('相电流 (A)', fontsize=10, color='r')
        ax3.set_title('电流-转矩曲线（线性关系）', fontsize=11, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper left', fontsize=8)
        ax3.set_xlim(0, T_max)
        
        # 图4: 输出功率
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.plot(torques, powers_out, 'm-', linewidth=2)
        ax4.axhline(y=p["P_rated"], color='m', linestyle='--', alpha=0.5,
                   label=f'额定: {p["P_rated"]:.0f} W')
        ax4.set_xlabel('转矩 (Nm)', fontsize=10)
        ax4.set_ylabel('输出功率 (W)', fontsize=10, color='m')
        ax4.set_title('功率-转矩曲线', fontsize=11, fontweight='bold')
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc='upper right', fontsize=8)
        ax4.set_xlim(0, T_max)
        
        fig.suptitle('电机性能特性曲线', fontsize=12, fontweight='bold')
        
        self._register_figure("performance_curves", fig)
        canvas = FigureCanvasTkAgg(fig, master=self.curves_tab)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, self.curves_tab)
        toolbar.update()
        
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _plot_back_emf(self):
        """绘制反电动势波形"""
        self._clear_tab(self.emf_tab)
        self._clear_figure("back_emf")
            
        if not self.calc_results:
            return

        if not MATPLOTLIB_AVAILABLE:
            self._set_chart_placeholder(
                self.emf_tab,
                "反电动势图表不可用",
                "当前环境未安装 matplotlib，反电动势波形和 FFT 图表已禁用。",
            )
            return
            
        emf_data = self.calc_results.waveforms.get("back_emf", {})
        if not emf_data:
            return
            
        fig = Figure(figsize=(12, 9), dpi=100)
        gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.3)
        
        t = emf_data["time"] * 1000  # 转换为ms
        theta = emf_data["theta_m"]
        
        # 图1: 三相反电动势
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(theta[:360], emf_data["E_a"][:360], 'r-', linewidth=1.5, label='A相')
        ax1.plot(theta[:360], emf_data["E_b"][:360], 'g-', linewidth=1.5, label='B相')
        ax1.plot(theta[:360], emf_data["E_c"][:360], 'b-', linewidth=1.5, label='C相')
        ax1.set_xlabel('机械角度 (度)', fontsize=10)
        ax1.set_ylabel('反电动势 (V)', fontsize=10)
        ax1.set_title('三相反电动势波形', fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=9)
        ax1.axhline(y=0, color='k', linewidth=0.5)
        
        # 添加标注
        E_peak = emf_data["E_peak"]
        E_rms = emf_data["E_rms"]
        ax1.annotate(f'峰值: {E_peak:.1f}V\n有效值: {E_rms:.1f}V', 
                    xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # 图2: 线电压反电动势
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.plot(theta[:360], emf_data["E_ab"][:360], 'purple', linewidth=1.5, label='E_ab')
        ax2.plot(theta[:360], emf_data["E_bc"][:360], 'orange', linewidth=1.5, label='E_bc')
        ax2.plot(theta[:360], emf_data["E_ca"][:360], 'cyan', linewidth=1.5, label='E_ca')
        ax2.set_xlabel('机械角度 (度)', fontsize=10)
        ax2.set_ylabel('线电压反电动势 (V)', fontsize=10)
        ax2.set_title('线电压反电动势', fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper right', fontsize=8)
        
        # 图3: 与理想正弦波对比
        ax3 = fig.add_subplot(gs[1, 1])
        ax3.plot(theta[:360], emf_data["E_a"][:360], 'r-', linewidth=1.5, label='实际波形')
        ax3.plot(theta[:360], emf_data["E_ideal"][:360], 'k--', linewidth=1, label='理想正弦')
        ax3.set_xlabel('机械角度 (度)', fontsize=10)
        ax3.set_ylabel('反电动势 (V)', fontsize=10)
        ax3.set_title('实际波形与理想正弦波对比', fontsize=11, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper right', fontsize=9)
        
        # 图4: FFT谐波分析
        ax4 = fig.add_subplot(gs[2, :])
        
        # 计算FFT
        E_a = emf_data["E_a"]
        N = len(E_a)
        fft_vals = np.fft.fft(E_a)
        fft_mag = np.abs(fft_vals[:N//2]) / N * 2
        
        p = self._get_params()
        poles = int(p["p"])
        harmonics = np.arange(N//2) * poles
        
        # 只绘制前25个显著谐波
        max_harmonic = 25
        valid_idx = harmonics <= max_harmonic
        
        ax4.bar(harmonics[valid_idx], fft_mag[valid_idx], width=0.6, color='steelblue', alpha=0.8)
        ax4.set_xlabel('谐波次数', fontsize=10)
        ax4.set_ylabel('幅值 (V)', fontsize=10)
        ax4.set_title('反电动势谐波分析 (FFT)', fontsize=11, fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')
        ax4.set_xlim(-0.5, max_harmonic + 0.5)
        
        # 计算THD
        fundamental = fft_mag[1] if len(fft_mag) > 1 else 1
        harmonics_sum = np.sqrt(np.sum(fft_mag[2:20]**2))
        thd = (harmonics_sum / fundamental * 100) if fundamental > 0 else 0
        ax4.annotate(f'THD: {thd:.1f}%', xy=(0.95, 0.95), xycoords='axes fraction',
                    fontsize=10, ha='right', va='top',
                    bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        fig.suptitle('反电动势分析', fontsize=12, fontweight='bold')
        
        self._register_figure("back_emf", fig)
        canvas = FigureCanvasTkAgg(fig, master=self.emf_tab)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, self.emf_tab)
        toolbar.update()
        
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _plot_torque(self):
        """绘制转矩分析"""
        self._clear_tab(self.torque_tab)
        self._clear_figure("torque")
            
        if not self.calc_results:
            return

        if not MATPLOTLIB_AVAILABLE:
            self._set_chart_placeholder(
                self.torque_tab,
                "转矩图表不可用",
                "当前环境未安装 matplotlib，转矩波形、齿槽转矩和脉动分布图已禁用。",
            )
            return
            
        torque_data = self.calc_results.waveforms.get("torque", {})
        cogging_data = self.calc_results.waveforms.get("cogging", {})
        
        fig = Figure(figsize=(12, 8), dpi=100)
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # 图1: 瞬时转矩
        ax1 = fig.add_subplot(gs[0, :])
        theta = torque_data.get("theta_e", np.linspace(0, 720, 360))
        T_inst = torque_data.get("T_inst", np.zeros_like(theta))
        T_avg = torque_data.get("T_avg", 0)
        
        ax1.plot(theta, T_inst, 'b-', linewidth=1.5, label='瞬时转矩')
        ax1.axhline(y=T_avg, color='r', linestyle='--', linewidth=2, label=f'平均值: {T_avg:.3f} Nm')
        ax1.fill_between(theta, T_inst, T_avg, alpha=0.3, color='blue')
        ax1.set_xlabel('电角度 (度)', fontsize=10)
        ax1.set_ylabel('转矩 (Nm)', fontsize=10)
        ax1.set_title('电磁转矩-电角度曲线', fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=9)
        
        # 标注
        T_max = torque_data.get("T_max", T_avg)
        T_min = torque_data.get("T_min", T_avg)
        ripple = torque_data.get("T_ripple_pct", 0)
        ax1.annotate(f'最大值: {T_max:.3f} Nm\n最小值: {T_min:.3f} Nm\n脉动: {ripple:.1f}%',
                    xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # 图2: 齿槽转矩
        ax2 = fig.add_subplot(gs[1, 0])
        theta_cog = cogging_data.get("theta", np.linspace(0, 2*PI, 360))
        T_cog = cogging_data.get("T_cog", np.zeros_like(theta_cog))
        
        ax2.plot(np.degrees(theta_cog), T_cog * 1000, 'g-', linewidth=1.5)
        ax2.set_xlabel('转子位置 (度)', fontsize=10)
        ax2.set_ylabel('齿槽转矩 (mNm)', fontsize=10)
        ax2.set_title('齿槽转矩-转子位置曲线', fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='k', linewidth=0.5)
        
        T_cog_peak = np.max(np.abs(T_cog)) * 1000
        ax2.annotate(f'峰值: ±{T_cog_peak:.2f} mNm',
                    xy=(0.95, 0.95), xycoords='axes fraction',
                    fontsize=9, ha='right', va='top',
                    bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))
        
        # 图3: 转矩脉动直方图
        ax3 = fig.add_subplot(gs[1, 1])
        ripple_vals = (T_inst - T_avg) / T_avg * 100
        ax3.hist(ripple_vals, bins=30, color='steelblue', alpha=0.7, edgecolor='black')
        ax3.axvline(x=0, color='r', linestyle='--', linewidth=2)
        ax3.set_xlabel('相对平均值偏差 (%)', fontsize=10)
        ax3.set_ylabel('频次', fontsize=10)
        ax3.set_title('转矩脉动分布直方图', fontsize=11, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        fig.suptitle('转矩分析', fontsize=12, fontweight='bold')
        
        self._register_figure("torque", fig)
        canvas = FigureCanvasTkAgg(fig, master=self.torque_tab)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, self.torque_tab)
        toolbar.update()
        
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _plot_flux_distribution(self):
        """绘制气隙磁密分布"""
        self._clear_tab(self.flux_tab)
        self._clear_figure("flux_distribution")
            
        if not self.calc_results:
            return

        if not MATPLOTLIB_AVAILABLE:
            self._set_chart_placeholder(
                self.flux_tab,
                "磁密图表不可用",
                "当前环境未安装 matplotlib，磁密分布与谐波图表已禁用。",
            )
            return
            
        flux_data = self.calc_results.waveforms.get("flux", {})
        
        fig = Figure(figsize=(12, 8), dpi=100)
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # 图1: 磁密分布
        ax1 = fig.add_subplot(gs[0, :])
        theta_m = flux_data.get("theta_m", np.linspace(0, 360, 720))
        Bg = flux_data.get("Bg", np.zeros_like(theta_m))
        
        ax1.plot(theta_m, Bg, 'b-', linewidth=1.5)
        ax1.fill_between(theta_m, Bg, 0, where=(Bg > 0), color='blue', alpha=0.3, label='N极')
        ax1.fill_between(theta_m, Bg, 0, where=(Bg < 0), color='red', alpha=0.3, label='S极')
        ax1.set_xlabel('机械角度 (度)', fontsize=10)
        ax1.set_ylabel('气隙磁密 (T)', fontsize=10)
        ax1.set_title('气隙磁密分布', fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=9)
        ax1.axhline(y=0, color='k', linewidth=0.5)
        
        # 标注
        Bg_peak = flux_data.get("Bg_peak", 0)
        Bg_avg = flux_data.get("Bg_avg", 0)
        Bg_rms = flux_data.get("Bg_rms", 0)
        ax1.annotate(f'峰值: {Bg_peak:.3f} T\n平均值: {Bg_avg:.3f} T\n有效值: {Bg_rms:.3f} T',
                    xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # 图2: 谐波分析
        ax2 = fig.add_subplot(gs[1, 0])
        # Phase 9B B1: plot against the explicit ELECTRICAL harmonic order so the
        # fundamental lands at 1 for every pole count. The old `harmonics` key
        # carried k * pole_pairs and filtered the fundamental out for p >= 5.
        harmonics = flux_data.get(
            "electrical_harmonic_order", flux_data.get("harmonics", np.arange(20))
        )
        spectrum = flux_data.get("spectrum", np.zeros(20))

        valid_idx = harmonics <= 25
        ax2.bar(harmonics[valid_idx], spectrum[valid_idx], width=0.02 + 0.6 / max(len(harmonics), 1), color='steelblue', alpha=0.8)
        ax2.set_xlabel('电气空间谐波次数（基波 = 1）', fontsize=10)
        ax2.set_ylabel('幅值 (T)', fontsize=10)
        ax2.set_title('磁密空间谐波分析', fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # 图3: 极坐标图
        ax3 = fig.add_subplot(gs[1, 1], projection='polar')
        theta_rad = np.radians(theta_m)
        
        # 归一化用于极坐标绘图
        Bg_norm = (Bg - np.min(Bg)) / (np.max(Bg) - np.min(Bg) + 1e-10)
        
        ax3.plot(theta_rad, Bg_norm, 'b-', linewidth=1)
        ax3.fill(theta_rad, Bg_norm, alpha=0.3)
        ax3.set_title('磁密分布（极坐标视图）', fontsize=11, fontweight='bold', pad=20)
        
        fig.suptitle('磁场分析', fontsize=12, fontweight='bold')
        
        self._register_figure("flux_distribution", fig)
        canvas = FigureCanvasTkAgg(fig, master=self.flux_tab)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, self.flux_tab)
        toolbar.update()
        
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _draw_geometry(self):
        """绘制电机截面几何结构"""
        self._clear_tab(self.geo_tab)
        self._clear_figure("geometry")

        if not MATPLOTLIB_AVAILABLE:
            self._set_chart_placeholder(
                self.geo_tab,
                "几何图不可用",
                "当前环境未安装 matplotlib，几何结构可视化与图表保存功能已禁用。",
            )
            return
            
        p = self._get_params()
        
        fig = Figure(figsize=(12, 6), dpi=100)
        
        # 径向截面（左）
        ax1 = fig.add_subplot(121)
        
        D_o = p["D_out"]
        D_i = p["D_in"]
        h_m = p["h_mag"]
        h_c = p["h_coil"]
        g = p["g_side"]
        
        # 绘制各部件（径向截面）
        y_base = 0
        yoke_thickness = 5  # mm
        
        # 底部转子轭
        ax1.add_patch(patches.Rectangle((0, y_base), D_o/2, yoke_thickness, 
                                        color='gray', label='转子轭'))
        y_base += yoke_thickness
        
        # 底部永磁体
        ax1.add_patch(patches.Rectangle((D_i/2, y_base), (D_o-D_i)/2, h_m, 
                                        color='blue', label='永磁体 (N)'))
        y_base += h_m
        
        # 底部气隙
        ax1.add_patch(patches.Rectangle((D_i/2, y_base), (D_o-D_i)/2, g, 
                                        color='white', edgecolor='black', linestyle='--'))
        y_base += g
        
        # 定子线圈
        ax1.add_patch(patches.Rectangle((D_i/2 * 0.9, y_base), (D_o-D_i)/2 * 1.1, h_c, 
                                        color='orange', alpha=0.7, label='定子线圈'))
        y_base += h_c
        
        # 顶部气隙
        ax1.add_patch(patches.Rectangle((D_i/2, y_base), (D_o-D_i)/2, g, 
                                        color='white', edgecolor='black', linestyle='--'))
        y_base += g
        
        # 顶部永磁体
        ax1.add_patch(patches.Rectangle((D_i/2, y_base), (D_o-D_i)/2, h_m, 
                                        color='red', label='永磁体 (S)'))
        y_base += h_m
        
        # 顶部转子轭
        ax1.add_patch(patches.Rectangle((0, y_base), D_o/2, yoke_thickness, 
                                        color='gray'))
        
        ax1.set_xlim(-5, D_o/2 * 1.3)
        ax1.set_ylim(-2, y_base + yoke_thickness + 5)
        ax1.set_aspect('equal')
        ax1.set_xlabel('半径 (mm)', fontsize=10)
        ax1.set_ylabel('轴向位置 (mm)', fontsize=10)
        ax1.set_title('径向截面图（半剖）', fontsize=11, fontweight='bold')
        ax1.legend(loc='upper right', fontsize=8)
        ax1.grid(True, alpha=0.3)
        
        # 添加尺寸标注
        ax1.annotate('', xy=(D_o/2, -1), xytext=(0, -1),
                    arrowprops=dict(arrowstyle='<->', color='black'))
        ax1.text(D_o/4, -3, f'R_out={D_o/2:.0f}mm', ha='center', fontsize=8)
        
        # 轴向视图（右）- 显示极分布
        ax2 = fig.add_subplot(122, projection='polar')
        
        poles = int(p["p"]) * 2
        alpha = p["alpha_p"]
        
        pole_pitch = 2 * PI / poles
        magnet_arc = pole_pitch * alpha
        
        for i in range(poles):
            start_angle = i * pole_pitch
            color = 'blue' if i % 2 == 0 else 'red'
            
            theta = np.linspace(start_angle, start_angle + magnet_arc, 50)
            r_inner = np.full_like(theta, D_i/2)
            r_outer = np.full_like(theta, D_o/2)
            
            ax2.fill_between(theta, r_inner, r_outer, color=color, alpha=0.6)
        
        ax2.set_ylim(0, D_o/2 * 1.1)
        ax2.set_title(f'轴向视图 ({poles} 极)', fontsize=11, fontweight='bold', pad=20)
        
        fig.suptitle('电机几何结构可视化', fontsize=12, fontweight='bold')
        
        self._register_figure("geometry", fig)
        canvas = FigureCanvasTkAgg(fig, master=self.geo_tab)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, self.geo_tab)
        toolbar.update()
        
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def run_optimization(self):
        """运行自动设计优化"""
        # RC2 P0-2: `V_required` 是线电压 RMS 需求，必须与同基的线性 SVPWM 电压
        # 包络 Vdc/sqrt(2) 比较，而不是直接与直流母线电压 Vdc 比较。
        # Phase 9C: 进一步把所需电压本身切换为修正的单一基准稳态相量值；
        # legacy 混合基准值只作为兼容参考展示，不再参与接受判据或排序。
        from motor_calculator.validation.design_feasibility import (
            evaluate_design_feasibility,
            same_basis_available_line_rms_v,
        )

        try:
            params = self._get_params()
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "=" * 60 + "\n")
            self.result_text.insert(tk.END, "   自动设计优化\n")
            self.result_text.insert(tk.END, "=" * 60 + "\n\n")
            self.result_text.insert(tk.END, "正在搜索最优配置...\n\n")
            self.root.update()
            
            best_score = -float('inf')
            best_params = None
            best_results = None
            
            # RC2 P0-2: 电压利用率目标同样必须落在同基包络内。旧实现以 0.85*Vdc
            # 为目标线电压 RMS，该目标本身已超出 Vdc/sqrt(2) 包络。
            available_line_rms_V = same_basis_available_line_rms_v(params["V_dc"])
            target_V = available_line_rms_V * 0.85  # 目标：同基可用线电压 RMS 的 85%
            
            optimization_log = []
            
            # 优化循环: 改变匝数和并联根数
            for N_try in range(15, 120, 3):
                params["N_ph_turns"] = N_try
                
                # 第一轮估算电流
                params["n_parallel"] = 1
                try:
                    model = PMDCMotorModel(params)
                    temp_results = model.run_full_analysis()
                except:
                    continue
                
                I_est = temp_results.performance.I_phase_rms
                
                # 计算所需并联根数以使 J ≈ 5 A/mm²
                d_wire = params["d_wire"] * 1e-3
                A_single = PI * (d_wire/2)**2 * 1e6  # mm²
                n_par_needed = max(1, round(I_est / (5.5 * A_single)))
                n_par_needed = min(n_par_needed, 10)  # 实际限制
                
                params["n_parallel"] = n_par_needed
                
                # 使用调整后参数进行完整计算
                try:
                    model = PMDCMotorModel(params)
                    results = model.run_full_analysis()
                except:
                    continue
                
                # 评分函数
                score = 0
                perf = results.performance
                
                # 硬约束（重罚）。Phase 9C: 使用修正同基所需电压。
                candidate_assessment = evaluate_design_feasibility(params, results)
                candidate_required_v = candidate_assessment.required_voltage_line_rms_v
                if candidate_required_v is None:
                    continue
                if candidate_required_v > available_line_rms_V:
                    score -= 10000
                # RC2 P0-1: legacy K_fill 是内圆周线宽比例，不是槽满率，且对任何
                # 现实设计都远大于 1，因此旧约束恒定命中、不携带任何信息。改为使用
                # Phase 8G 的近似裸铜槽占比；槽几何不足时不施加槽面积惩罚。
                candidate_occupancy = candidate_assessment.slot_fill_factor
                if candidate_occupancy is not None and candidate_occupancy > params["fill_limit"]:
                    score -= 5000
                if perf.J_current > 8:
                    score -= 2000
                elif perf.J_current > 6:
                    score -= 500
                
                # 软目标
                score += perf.Efficiency * 10  # 最大化效率
                score -= abs(target_V - candidate_required_v) * 2  # 电压利用率（修正同基）
                score -= perf.T_ripple * 10  # 最小化转矩脉动
                
                optimization_log.append({
                    "N": N_try,
                    "n_par": n_par_needed,
                    "V_req": candidate_required_v,
                    "legacy_V_req": perf.V_required,
                    "J": perf.J_current,
                    "Eff": perf.Efficiency,
                    "legacy_K_fill": perf.K_fill,
                    "slot_occupancy": candidate_occupancy,
                    "Score": score
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_results = results
            
            if best_results:
                # 使用最优值更新输入字段
                self.vars["N_ph_turns"].set(str(int(best_params["N_ph_turns"])))
                self.vars["n_parallel"].set(str(int(best_params["n_parallel"])))
                
                self.calc_results = best_results
                
                # 显示优化结果
                self.result_text.insert(tk.END, "优化完成！\n")
                self.result_text.insert(tk.END, "-" * 50 + "\n\n")
                self.result_text.insert(tk.END, "推荐设计参数:\n")
                self.result_text.insert(tk.END, f"  • 每相匝数: {int(best_params['N_ph_turns'])}\n")
                self.result_text.insert(tk.END, f"  • 并联根数: {int(best_params['n_parallel'])}\n\n")
                
                perf = best_results.performance
                # RC2 P0-1/P0-2: 面向用户的可行性结论一律来自 Phase 8G 同基评估，
                # legacy V_margin / K_fill 仅作为兼容值显式标注保留。
                best_assessment = evaluate_design_feasibility(best_params, best_results)
                self.result_text.insert(tk.END, "优化后性能:\n")
                self.result_text.insert(tk.END, f"  • 效率: {perf.Efficiency:.2f}%\n")
                self.result_text.insert(tk.END, f"  • 电流密度: {perf.J_current:.2f} A/mm²\n")
                if best_assessment.voltage_margin_percent is None:
                    self.result_text.insert(
                        tk.END,
                        f"  • 同基电压裕量: 信息不足（{best_assessment.voltage_status.value}）\n",
                    )
                else:
                    self.result_text.insert(
                        tk.END,
                        f"  • 所需线电压 RMS: {best_assessment.required_voltage_line_rms_v:.2f} V\n",
                    )
                    self.result_text.insert(
                        tk.END,
                        f"  • 可用线电压 RMS: {best_assessment.available_voltage_line_rms_v:.2f} V\n",
                    )
                    self.result_text.insert(
                        tk.END,
                        f"  • 同基电压裕量: {best_assessment.voltage_margin_percent:.1f}%\n",
                    )
                if best_assessment.slot_fill_factor is None:
                    self.result_text.insert(
                        tk.END,
                        f"  • 近似裸铜槽占比: 信息不足（{best_assessment.slot_fill_status.value}）\n",
                    )
                else:
                    self.result_text.insert(
                        tk.END,
                        f"  • 近似裸铜槽占比: {best_assessment.slot_fill_factor:.4f}"
                        f"（{best_assessment.slot_fill_factor * 100.0:.1f}%）\n",
                    )
                self.result_text.insert(tk.END, f"  • 转矩脉动: {perf.T_ripple:.2f}%\n")
                self.result_text.insert(
                    tk.END,
                    f"  • 兼容值 legacy 所需线电压 RMS: {perf.V_required:.2f} V（混合基准，仅供参考）\n",
                )
                self.result_text.insert(
                    tk.END,
                    f"  • 兼容值 legacy 直流母线差额: {perf.V_margin:.1f}%（非工程结论）\n",
                )
                self.result_text.insert(
                    tk.END,
                    f"  • Legacy 线性绕组占比: {perf.K_fill:.3f}（兼容值，非槽满率）\n\n",
                )
                
                # 显示完整报告
                self._display_report()
                self._plot_performance_curves()
                self._plot_back_emf()
                self._plot_torque()
                self._plot_flux_distribution()
                self._draw_geometry()
                
            else:
                self.result_text.insert(tk.END, "优化失败\n")
                self.result_text.insert(tk.END, "无法找到可行的设计点。\n")
                self.result_text.insert(tk.END, "请检查几何约束条件。\n")
                
        except Exception as e:
            messagebox.showerror("优化错误", f"优化失败:\n{str(e)}")
    
    def export_json(self):
        """导出计算数据为JSON文件"""
        if not self.calc_results:
            messagebox.showwarning("无数据", "请先运行分析。")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            title="保存计算数据"
        )
        
        if filepath:
            # RC2 STEP 22: the legacy kernel keys keep their historical meaning,
            # so an explicit, unambiguously named section carries the
            # authoritative same-basis metrics instead of renaming them.
            rc2_payload = getattr(self, "rc2_export_payload", None)
            data = {
                "输入参数": self._get_params(),
                "RC2工程结论": rc2_payload() if callable(rc2_payload) else None,
                "计算结果": self.calc_results.to_dict(),
                "波形数据": {
                    "反电动势": {k: v.tolist() if isinstance(v, np.ndarray) else v 
                                for k, v in self.calc_results.waveforms.get("back_emf", {}).items()},
                    "转矩": {k: v.tolist() if isinstance(v, np.ndarray) else v 
                              for k, v in self.calc_results.waveforms.get("torque", {}).items()},
                    "磁密": {k: v.tolist() if isinstance(v, np.ndarray) else v 
                            for k, v in self.calc_results.waveforms.get("flux", {}).items()}
                }
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            messagebox.showinfo("导出完成", f"数据已保存至:\n{filepath}")
    
    def export_csv(self):
        """导出计算数据为CSV文件"""
        if not self.calc_results:
            messagebox.showwarning("无数据", "请先运行分析。")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            title="保存计算数据"
        )
        
        if filepath:
            r = self.calc_results
            p = self._get_params()
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 标题
                writer.writerow(["永磁直流电机计算结果"])
                writer.writerow(["生成时间", datetime.now().isoformat()])
                writer.writerow([])
                
                # 输入参数
                writer.writerow(["输入参数"])
                for key, value in p.items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                # 磁路结果
                writer.writerow(["磁路计算结果"])
                writer.writerow(["峰值气隙磁密 (T)", r.magnetic.Bg_peak])
                writer.writerow(["平均磁密 (T)", r.magnetic.Bg_avg])
                writer.writerow(["每极磁通 (Wb)", r.magnetic.Phi_pole])
                writer.writerow(["磁导系数", r.magnetic.PC])
                writer.writerow([])
                
                # 电气参数
                writer.writerow(["电气参数"])
                writer.writerow(["相电阻 (Ω)", r.electrical.R_phase])
                writer.writerow(["相电感 (H)", r.electrical.L_phase])
                writer.writerow(["反电势常数 (V/krpm)", r.electrical.Ke])
                writer.writerow(["转矩常数 (Nm/A)", r.electrical.Kt])
                writer.writerow([])
                
                # 性能指标
                writer.writerow(["性能指标"])
                writer.writerow(["效率 (%)", r.performance.Efficiency])
                writer.writerow(["额定转矩 (Nm)", r.performance.T_rated])
                writer.writerow(["相电流 (A)", r.performance.I_phase_rms])
                writer.writerow(["电流密度 (A/mm²)", r.performance.J_current])
                writer.writerow(["铜损 (W)", r.performance.P_cu])
                writer.writerow(["涡流损耗 (W)", r.performance.P_eddy])
                writer.writerow([])

                # RC2 STEP 22: authoritative same-basis metrics with
                # unambiguous names.
                writer.writerow(["RC2 工程结论（同基口径）"])
                rc2_payload = getattr(self, "rc2_export_payload", None)
                rc2 = rc2_payload() if callable(rc2_payload) else {}
                for key in (
                    "slot_occupancy_ratio",
                    "slot_occupancy_percent",
                    "slot_occupancy_status",
                    "voltage_margin_same_basis_percent",
                    "voltage_available_line_rms_v",
                    "voltage_required_line_rms_v",
                    "winding_factor",
                    "winding_factor_mode",
                    "winding_factor_provenance",
                    "legacy_linear_winding_proxy",
                    "legacy_dc_bus_difference_percent",
                ):
                    writer.writerow([key, rc2.get(key)])
                
            messagebox.showinfo("导出完成", f"数据已保存至:\n{filepath}")
    
    def _export_txt(self):
        """导出报告为TXT文件"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="保存报告"
        )
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.result_text.get(1.0, tk.END))
            messagebox.showinfo("保存成功", f"报告已保存至:\n{filepath}")
    
    def _export_full_txt(self):
        """导出完整数据为TXT文件（包含波形数据）"""
        if not self.calc_results:
            messagebox.showwarning("无数据", "请先运行分析。")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="导出完整数据"
        )
        
        if filepath:
            r = self.calc_results
            p = self._get_params()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                # 报告头
                f.write("=" * 80 + "\n")
                f.write("   永磁直流/无刷直流电机电磁分析完整数据报告\n")
                f.write("=" * 80 + "\n")
                f.write(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"   模型版本: {r.metadata.get('模型版本', '6.0')}\n")
                f.write("=" * 80 + "\n\n")
                
                # 第一部分：输入参数
                f.write("第一部分：输入参数\n")
                f.write("-" * 60 + "\n")
                for key, value in p.items():
                    f.write(f"   {key}: {value}\n")
                f.write("\n")
                
                # 第二部分：定子几何参数
                f.write("第二部分：定子几何参数\n")
                f.write("-" * 60 + "\n")
                f.write(f"   定子外径: {r.stator_geo.D_stator_out * 1000:.1f} mm\n")
                f.write(f"   定子内径: {r.stator_geo.D_stator_in * 1000:.1f} mm\n")
                f.write(f"   定子叠厚: {r.stator_geo.h_stator * 1000:.1f} mm\n")
                f.write(f"   定子轭部高度: {r.stator_geo.h_yoke * 1000:.1f} mm\n")
                f.write(f"   槽数: {r.stator_geo.slots}\n")
                f.write(f"   槽形类型: {r.stator_geo.slot_type}\n")
                f.write(f"   槽距: {r.stator_geo.slot_pitch * 1000:.2f} mm\n")
                f.write("\n")
                
                # 第三部分：槽形几何参数
                f.write("第三部分：槽形几何参数\n")
                f.write("-" * 60 + "\n")
                f.write(f"   槽深: {r.slot_geo.h_slot * 1000:.1f} mm\n")
                f.write(f"   槽口宽度: {r.slot_geo.w_slot_top * 1000:.1f} mm\n")
                f.write(f"   槽底宽度: {r.slot_geo.w_slot_bottom * 1000:.1f} mm\n")
                f.write(f"   槽口高度: {r.slot_geo.h_slot_opening * 1000:.1f} mm\n")
                f.write(f"   槽口开口宽度: {r.slot_geo.w_slot_opening * 1000:.1f} mm\n")
                f.write(f"   槽楔高度: {r.slot_geo.h_wedge * 1000:.1f} mm\n")
                f.write(f"   槽面积: {r.slot_geo.slot_area * 1e6:.2f} mm²\n")
                f.write("\n")
                
                # 第四部分：永磁体几何参数
                f.write("第四部分：永磁体几何参数\n")
                f.write("-" * 60 + "\n")
                f.write(f"   永磁体厚度: {r.magnet_geo.h_magnet * 1000:.1f} mm\n")
                f.write(f"   永磁体宽度（周向）: {r.magnet_geo.w_magnet * 1000:.1f} mm\n")
                f.write(f"   永磁体长度（径向）: {r.magnet_geo.L_magnet * 1000:.1f} mm\n")
                f.write(f"   永磁体类型: {r.magnet_geo.magnet_type}\n")
                f.write(f"   充磁方式: {r.magnet_geo.magnetization}\n")
                f.write(f"   单块永磁体体积: {r.magnet_geo.magnet_volume * 1e9:.2f} mm³\n")
                f.write("\n")
                
                # 第五部分：磁路计算结果
                f.write("第五部分：磁路计算结果\n")
                f.write("-" * 60 + "\n")
                f.write(f"   峰值气隙磁密 (Bg_peak): {r.magnetic.Bg_peak:.6f} T\n")
                f.write(f"   平均磁密 (Bg_avg): {r.magnetic.Bg_avg:.6f} T\n")
                f.write(f"   均方根磁密 (Bg_rms): {r.magnetic.Bg_rms:.6f} T\n")
                f.write(f"   每极磁通 (Φ): {r.magnetic.Phi_pole:.6e} Wb\n")
                f.write(f"   磁导系数 (PC): {r.magnetic.PC:.4f}\n")
                f.write(f"   气隙磁阻: {r.magnetic.R_gap:.6e} A/Wb\n")
                f.write(f"   永磁体磁阻: {r.magnetic.R_mag:.6e} A/Wb\n")
                f.write(f"   永磁体磁动势: {r.magnetic.Fm:.2f} A\n")
                f.write("\n")
                
                # 第六部分：电气参数
                f.write("第六部分：电气参数\n")
                f.write("-" * 60 + "\n")
                f.write(f"   相电阻 (R_ph): {r.electrical.R_phase:.6f} Ω\n")
                f.write(f"   线电阻 (R_line): {r.electrical.R_line:.6f} Ω\n")
                f.write(f"   相电感 (L_ph): {r.electrical.L_phase:.6e} H\n")
                f.write(f"   线电感 (L_line): {r.electrical.L_line:.6e} H\n")
                f.write(f"   互感 (M): {r.electrical.M_mutual:.6e} H\n")
                f.write(f"   相反电势有效值 (E_ph): {r.electrical.E_phase_rms:.4f} V\n")
                f.write(f"   线反电势有效值 (E_line): {r.electrical.E_line_rms:.4f} V\n")
                f.write(f"   反电势常数 (Ke): {r.electrical.Ke:.4f} V/krpm\n")
                f.write(f"   转矩常数 (Kt): {r.electrical.Kt:.6f} Nm/A\n")
                f.write("\n")
                
                # 第七部分：性能指标
                f.write("第七部分：性能指标\n")
                f.write("-" * 60 + "\n")
                f.write(f"   额定转矩: {r.performance.T_rated:.6f} Nm\n")
                f.write(f"   平均转矩: {r.performance.T_avg:.6f} Nm\n")
                f.write(f"   转矩脉动: {r.performance.T_ripple:.2f} %\n")
                f.write(f"   峰值齿槽转矩: {r.performance.T_cogging_peak:.6f} Nm\n")
                f.write(f"   相电流有效值: {r.performance.I_phase_rms:.4f} A\n")
                f.write(f"   线电流有效值: {r.performance.I_line_rms:.4f} A\n")
                f.write(f"   电流密度: {r.performance.J_current:.4f} A/mm²\n")
                f.write(f"   输出功率: {r.performance.P_out:.2f} W\n")
                f.write(f"   输入功率: {r.performance.P_in:.2f} W\n")
                f.write(f"   铜损: {r.performance.P_cu:.2f} W\n")
                f.write(f"   涡流损耗: {r.performance.P_eddy:.2f} W\n")
                f.write(f"   机械损耗: {r.performance.P_mech:.2f} W\n")
                f.write(f"   铁损: {r.performance.P_core:.2f} W\n")
                f.write(f"   效率: {r.performance.Efficiency:.4f} %\n")
                f.write(f"   所需电压: {r.performance.V_required:.2f} V\n")
                # RC2 P0-1/P0-2: 导出必须使用同基 Phase 8G 语义；legacy 指标保留
                # 但显式标注，不得以 slot_fill_factor / 电压裕量 之名导出。
                try:
                    from motor_calculator.validation.design_feasibility import (
                        evaluate_design_feasibility as _evaluate_feasibility,
                    )

                    _fa = _evaluate_feasibility(self._get_params(), r)
                except Exception:
                    _fa = None
                if _fa is None or _fa.voltage_margin_percent is None:
                    f.write("   同基电压裕量: 信息不足\n")
                else:
                    f.write(
                        f"   同基电压裕量: {_fa.voltage_margin_percent:.2f} %"
                        f" (可用线电压 RMS {_fa.available_voltage_line_rms_v:.4f} V)\n"
                    )
                if _fa is None or _fa.slot_fill_factor is None:
                    _status = "NOT_ENOUGH_GEOMETRY" if _fa is None else _fa.slot_fill_status.value
                    f.write(f"   近似裸铜槽占比: 信息不足 ({_status})\n")
                else:
                    f.write(
                        f"   近似裸铜槽占比: {_fa.slot_fill_factor:.4f}"
                        f" ({_fa.slot_fill_factor * 100.0:.2f} %)\n"
                    )
                f.write(f"   Legacy 直流母线差额: {r.performance.V_margin:.2f} % (兼容值，非工程结论)\n")
                f.write(f"   Legacy 线性绕组占比: {r.performance.K_fill:.4f} (兼容值，非槽满率)\n")
                f.write("\n")
                
                # 第八部分：波形数据
                f.write("第八部分：波形数据\n")
                f.write("-" * 60 + "\n")
                
                # 反电动势波形数据
                emf_data = r.waveforms.get("back_emf", {})
                if emf_data:
                    f.write("\n--- 反电动势波形数据 ---\n")
                    f.write(f"峰值: {emf_data.get('E_peak', 0):.4f} V\n")
                    f.write(f"有效值: {emf_data.get('E_rms', 0):.4f} V\n")
                    f.write("\n机械角度(度), A相(V), B相(V), C相(V), 线电压AB(V)\n")
                    theta_m = emf_data.get("theta_m", [])
                    E_a = emf_data.get("E_a", [])
                    E_b = emf_data.get("E_b", [])
                    E_c = emf_data.get("E_c", [])
                    E_ab = emf_data.get("E_ab", [])
                    for i in range(min(360, len(theta_m))):
                        f.write(f"{theta_m[i]:.2f}, {E_a[i]:.4f}, {E_b[i]:.4f}, {E_c[i]:.4f}, {E_ab[i]:.4f}\n")
                
                # 转矩波形数据
                torque_data = r.waveforms.get("torque", {})
                if torque_data:
                    f.write("\n--- 转矩波形数据 ---\n")
                    f.write(f"平均转矩: {torque_data.get('T_avg', 0):.6f} Nm\n")
                    f.write(f"最大转矩: {torque_data.get('T_max', 0):.6f} Nm\n")
                    f.write(f"最小转矩: {torque_data.get('T_min', 0):.6f} Nm\n")
                    f.write(f"转矩脉动: {torque_data.get('T_ripple_pct', 0):.2f} %\n")
                    f.write("\n电角度(度), 瞬时转矩(Nm)\n")
                    theta_e = torque_data.get("theta_e", [])
                    T_inst = torque_data.get("T_inst", [])
                    for i in range(min(360, len(theta_e))):
                        f.write(f"{theta_e[i]:.2f}, {T_inst[i]:.6f}\n")
                
                # 磁密分布数据
                flux_data = r.waveforms.get("flux", {})
                if flux_data:
                    f.write("\n--- 气隙磁密分布数据 ---\n")
                    f.write(f"峰值磁密: {flux_data.get('Bg_peak', 0):.6f} T\n")
                    f.write(f"平均磁密: {flux_data.get('Bg_avg', 0):.6f} T\n")
                    f.write(f"有效值磁密: {flux_data.get('Bg_rms', 0):.6f} T\n")
                    f.write("\n机械角度(度), 气隙磁密(T)\n")
                    theta_m = flux_data.get("theta_m", [])
                    Bg = flux_data.get("Bg", [])
                    for i in range(min(360, len(theta_m))):
                        f.write(f"{theta_m[i]:.2f}, {Bg[i]:.6f}\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("                    数据导出结束\n")
                f.write("=" * 80 + "\n")
                
            messagebox.showinfo("导出完成", f"完整数据已保存至:\n{filepath}")
    
    def save_plots(self):
        """保存所有图表为图像文件"""
        if not self.calc_results:
            messagebox.showwarning("无数据", "请先运行分析。")
            return

        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror(
                "图表功能不可用",
                "当前环境未安装 matplotlib，无法保存图表。请先安装可选依赖后再重试。",
            )
            return

        if not getattr(self, "generated_figures", {}):
            messagebox.showwarning("无图表", "当前没有可保存的图表，请先运行分析并生成图表。")
            return

        folder = filedialog.askdirectory(title="选择图表保存文件夹")

        if folder:
            output_dir = Path(folder)
            figure_specs = [
                ("performance_curves", "performance_curves.png", "性能曲线"),
                ("back_emf", "back_emf.png", "反电动势"),
                ("torque", "torque.png", "转矩分析"),
                ("flux_distribution", "flux_distribution.png", "磁密分布"),
                ("geometry", "geometry.png", "几何结构"),
            ]
            saved_files = []
            failed_items = []

            for key, filename, label in figure_specs:
                figure = self.generated_figures.get(key)
                if figure is None:
                    failed_items.append(f"{label}: 未生成")
                    continue

                output_path = output_dir / filename
                try:
                    figure.savefig(output_path, dpi=150, bbox_inches="tight")
                except Exception as exc:
                    failed_items.append(f"{label}: {exc}")
                    continue

                if output_path.exists() and output_path.stat().st_size > 0:
                    saved_files.append(str(output_path))
                else:
                    failed_items.append(f"{label}: 文件未生成")

            if saved_files and not failed_items:
                messagebox.showinfo("保存完成", "图表已成功保存:\n" + "\n".join(saved_files))
            elif saved_files:
                messagebox.showwarning(
                    "部分保存成功",
                    "以下图表已保存:\n"
                    + "\n".join(saved_files)
                    + "\n\n以下图表未保存:\n"
                    + "\n".join(failed_items),
                )
            else:
                messagebox.showerror("保存失败", "未生成任何图表文件。\n" + "\n".join(failed_items))
    
    def reset_defaults(self):
        """重置所有输入为默认值"""
        defaults = {
            "V_dc": "48.0", "P_rated": "800.0", "n_rated": "2500.0",
            "Temp_coil": "80.0", "D_out": "140.0", "D_in": "70.0",
            "h_mag": "5.0", "h_coil": "5.0", "g_side": "1.0",
            "D_stator_out": "138.0", "D_stator_in": "72.0",
            "h_stator": "20.0", "h_yoke": "5.0", "slots": "24",
            "h_slot": "15.0", "w_slot_top": "8.0", "w_slot_bottom": "6.0",
            "h_slot_opening": "1.0", "w_slot_opening": "3.0", "h_wedge": "2.0",
            "w_magnet": "20.0", "L_magnet": "30.0",
            "p": "8", "Br": "1.28", "alpha_p": "0.70", "sigma_m": "1.15",
            "mu_r_mag": "1.05",
            "N_ph_turns": "50", "d_wire": "0.9", "n_parallel": "2",
            "k_w": "0.93", "fill_limit": "0.65",
            "k_cogging": "0.02", "k_ripple_6": "0.05", "k_ripple_12": "0.02"
        }
        
        for key, value in defaults.items():
            if key in self.vars:
                self.vars[key].set(value)
                
        self.coreless_var.set(True)
        
        # 重置下拉框
        if "slot_type" in self.vars:
            self.vars["slot_type"].set("无槽")
        if "magnet_type" in self.vars:
            self.vars["magnet_type"].set("表贴式")
        if "magnetization" in self.vars:
            self.vars["magnetization"].set("径向充磁")
        if "waveform" in self.vars:
            self.vars["waveform"].set("正弦波")
        if "magnet_grade" in self.vars:
            self.vars["magnet_grade"].set("N42")
        
        messagebox.showinfo("重置完成", "所有参数已恢复默认值。")
        
    def _copy_report(self):
        """复制报告文本到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.result_text.get(1.0, tk.END))
        messagebox.showinfo("已复制", "报告已复制到剪贴板")
        
    def _save_report(self):
        """保存报告到文本文件"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="保存报告"
        )
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.result_text.get(1.0, tk.END))
            messagebox.showinfo("已保存", f"报告已保存至:\n{filepath}")
            
    def _print_report(self):
        """打印预览"""
        report_text = self.result_text.get(1.0, tk.END)
        
        # 创建打印预览窗口
        print_window = tk.Toplevel(self.root)
        print_window.title("打印预览")
        print_window.geometry("700x900")
        
        text = scrolledtext.ScrolledText(print_window, font=("Courier New", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, report_text)
        
        btn_frame = ttk.Frame(print_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text="复制到剪贴板", 
                  command=lambda: [self.root.clipboard_clear(), 
                                  self.root.clipboard_append(report_text)]).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="关闭", 
                  command=print_window.destroy).pack(side=tk.RIGHT)


# ==========================================
# 主程序入口
# ==========================================
def main():
    """应用程序入口点"""
    root = tk.Tk()
    
    # 设置窗口图标（如果有）
    try:
        root.iconbitmap("motor_icon.ico")
    except:
        pass
    
    app = MotorCalculatorApp(root)
    
    # 窗口居中
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()


if __name__ == "__main__":
    main()
