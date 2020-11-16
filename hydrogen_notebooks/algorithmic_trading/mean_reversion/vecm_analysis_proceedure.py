# %%

%load_ext autoreload
%autoreload 2

import os
import sys
import numpy
import pandas
from matplotlib import pyplot
from lib import regression as reg
from lib import stats
from lib import config
from lib import var
from lib import arima
from statsmodels.tsa.vector_ar import vecm
import statsmodels.api as sm
import statsmodels.formula.api as smf
import scipy
import datetime
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.vector_ar.vecm import VECM

pyplot.style.use(config.glyfish_style)

# %%

def multivariate_normal_sample(μ, Ω, n):
    return numpy.random.multivariate_normal(μ, Ω, n)

def comparison_plot(title, df, α, β, labels, box_pos, plot):
    samples = data_frame_to_samples(df)
    nplot, nsamples = samples.shape
    figure, axis = pyplot.subplots(figsize=(10, 7))
    axis.set_title(title)
    axis.set_xlabel(r"$t$")
    axis.set_xlim([0, nsamples-1])

    params = []
    d = ", "
    nα, _ = α.shape
    nβ, _ = β.shape
    for i in range(nα):
        params.append(f"$α_{{{i+1}}}$=[{d.join([format(elem, '2.2f') for elem in numpy.array(α[i]).flatten()])}]")
    for i in range(nβ):
        params.append(f"$β_{{{i+1}}}$=[{d.join([format(elem, '2.2f') for elem in numpy.array(β[i]).flatten()])}]")
    params_string = "\n".join(params)
    bbox = dict(boxstyle='square,pad=1', facecolor="#FEFCEC", edgecolor="#FEFCEC", alpha=0.75)
    axis.text(box_pos[0], box_pos[1], params_string, fontsize=15, bbox=bbox, transform=axis.transAxes)

    for i in range(nplot):
        axis.plot(range(nsamples), samples[i].T, label=labels[i], lw=1)
    axis.legend(fontsize=16)
    config.save_post_asset(figure, "mean_reversion", plot)

def regression_plot(title, xt, yt, labels, plot_name):
    nsample = len(xt)
    figure, axis = pyplot.subplots(figsize=(12, 8))
    axis.set_ylabel(labels[1])
    axis.set_xlabel(labels[0])
    x = numpy.linspace(numpy.min(xt), numpy.max(xt), 100)
    y_hat = x * params[1] + params[0]
    axis.set_title(title)
    axis.plot(xt, yt, marker='o', markersize=5.0, linestyle="None", markeredgewidth=1.0, alpha=0.75, zorder=5)
    axis.plot(x, y_hat, lw=3.0, color="#000000", zorder=6)
    config.save_post_asset(figure, "mean_reversion", plot_name)

def acf_pcf_plot(title, df, ylim, max_lag, plot):
    samples = data_frame_to_samples(df)
    vars = df.columns
    nplot, n = samples.shape
    figure, axis = pyplot.subplots(nplot/2, nplot/2, sharex=True, figsize=(12, 9))

    acf_values = acf(samples, max_lag)
    pacf_values = yule_walker(samples, max_lag)

    axis.set_title(title)
    axis.set_xlabel("Time Lag (τ)")
    axis.set_xlim([-0.1, max_lag])
    axis.set_ylim(ylim)
    axis.plot(range(max_lag+1), acf_values, label="ACF")
    axis.plot(range(1, max_lag+1), pacf_values, label="PACF")
    axis.legend(fontsize=16)
    config.save_post_asset(figure, "mean_reversion", plot)

# Implementation from Reduced Rank Regression For the Multivariate Linear Model
def covariance(x, y):
    _, n = x.shape
    cov = x[:,0]*y[:,0].T
    for i in range(1, n):
        cov += x[:,i]*y[:,i].T
    return cov/float(n)

def ols_residual(x, y):
    a = simple_multivariate_ols(x, y)
    return y-a*x

def vecm_anderson_form(samples):
    Δ = numpy.diff(samples)
    y = Δ[:,0:-1]
    z = Δ[:,1:]
    x = samples[:,1:-1]
    return y, x, z

def johansen_statistic(ρ2, n, r):
    m = len(ρ2)
    λ = numpy.log(numpy.ones(m-r)-ρ2[r:])
    return -n * numpy.sum(λ)

def johansen_statistic_critical_value(p, m, r):
    return scipy.stats.chi2.ppf(p, (m-r)**2)

def johansen_coint_theory(df, report=True):
    samples = data_frame_to_samples(df)
    m, n = samples.shape

    y, x, z = vecm_anderson_form(samples)

    x_star = ols_residual(z, x)
    y_star = ols_residual(z, y)

    d_star =  simple_multivariate_ols(z, y)

    Σxx = covariance(x_star, x_star)
    Σyy = covariance(y_star, y_star)
    Σxy = covariance(x_star, y_star)
    Σyx = covariance(y_star, x_star)

    sqrt_Σyy = numpy.matrix(scipy.linalg.sqrtm(Σyy))
    sqrt_Σyy_inv = numpy.matrix(numpy.linalg.inv(sqrt_Σyy))
    Σyy_inv = numpy.matrix(numpy.linalg.inv(Σyy))
    Σxx_inv = numpy.matrix(numpy.linalg.inv(Σxx))

    R = sqrt_Σyy_inv*Σyx*Σxx_inv*Σxy*sqrt_Σyy_inv

    ρ2, M = numpy.linalg.eig(R)
    idx = ρ2.argsort()[::-1]
    ρ2 = ρ2[idx]
    M = M[:,idx]

    rank = None
    for r in range(m):
        cv = johansen_statistic_critical_value(0.99, m, r)
        l = johansen_statistic(ρ2, n, r)
        if rank is None:
            print(f"Critical Value: {cv}, Trace Statistic: {l}")
        if l < cv:
            rank = r
            break

    α = sqrt_Σyy*M[:,:rank]
    β = M[:,:rank].T*sqrt_Σyy_inv*Σyx*numpy.matrix(numpy.linalg.inv(Σxx))

    if report:
        print(f"Rank={rank}")
        print("Eigen Values\n", ρ2)
        print("Eigen Vectors\n", M)
        print("α\n", α)
        print("β\n", β)

    if rank is None:
        print("Reduced Rank Solution Does Not Exist")
        return None

    return ρ2[:rank], M[:,:rank], α, β

# scipy implementation
def johansen_coint(df, report=True):
    samples = data_frame_to_samples(df)
    m, _  = samples.shape

    df = pandas.DataFrame(samples.T)
    result = vecm.coint_johansen(df, 0, 1)

    l = result.lr1
    cv = result.cvt

    # 0: 90%  1:95% 2: 99%
    rank = None
    for r in range(m):
        if report:
            print(f"Critical Value: {cv[r, 2]}, Trace Statistic: {l[r]}")
        if l[r] < cv[r, 2]:
            rank = r
            break

    ρ2 = result.eig
    M = numpy.matrix(result.evec)

    if report:
        print(f"Rank={rank}")
        print("Eigen Values\n", ρ2)
        print("Eigen Vectors\n", M)

    if rank is None:
        print("Reduced Rank Solution Does Not Exist")
        return None

    return ρ2[:rank], M[:,:rank]

# Data generation
def vecm_generate_sample(α, β, a, Ω, nsample):
    n, _ = a.shape
    xt = numpy.matrix(numpy.zeros((n, nsample)))
    εt = numpy.matrix(multivariate_normal_sample(numpy.zeros(n), Ω, nsample))
    for i in range(2, nsample):
        Δxt1 = xt[:,i-1] - xt[:,i-2]
        Δxt = α*β*xt[:,i-1] + a*Δxt1 + εt[i].T
        xt[:,i] = Δxt + xt[:,i-1]
    return samples_to_data_frame(xt)

def multivariate_test_sample(a, n, σ):
    m, _ = a.shape
    t = numpy.linspace(0.0, 10.0, n)
    x = numpy.matrix(t)
    for i in range(1, m):
        x = numpy.concatenate((x, numpy.matrix([t**(1/(i+1))])))
    ε = numpy.matrix(multivariate_normal_sample(numpy.zeros(m), σ*numpy.eye(m), n))
    y = a*x + ε.T
    return x, y

# Utilities
def acf(samples, nlags):
    return sm.tsa.stattools.acf(samples, nlags=nlags, fft=True)

def pacf(samples, nlags):
    return sm.tsa.stattools.pacf(samples, nlags=nlags, method="ywunbiased")

def simple_multivariate_ols(x, y):
    return covariance(y, x) * numpy.linalg.inv(covariance(x, x))

def multiple_ols(df, formula):
    return smf.ols(formula=formula, data=df).fit()

# Data trandformations
def samples_to_data_frame(samples):
    m, n = samples.shape
    columns = [f"x{i+1}" for i in range(m)]
    index = (pandas.date_range(pandas.Timestamp.now(tz="UTC"), periods=n) - pandas.Timedelta(days=n)).normalize()
    df = pandas.DataFrame(samples.T, columns=columns, index=index)
    return df

def data_frame_to_samples(df):
    return numpy.matrix(df.to_numpy()).T

def difference(df):
    return df.diff().dropna()

# Statistical tests
def residual_adf_test(df, params, report=True):
    samples = data_frame_to_samples(df)
    x = numpy.matrix(params[1:])*samples[1:,:]
    y = numpy.squeeze(numpy.asarray(samples[0,:]))
    εt = y - params[0] - numpy.squeeze(numpy.asarray(x))
    if report:
        return arima.adf_report(εt)
    else:
        return arima.adf_test(εt)

def sample_adf_test(df, report=True):
    results = []
    for c in df.columns:
        samples = df[c].to_numpy()
        if report:
            print(f">>> ADF Test Result for: {c}")
            results.append(arima.adf_report(samples))
            print("")
        else:
            results.append(arima.adf_test(samples))
    return results

# %%
# Test multivariate regression

n = 10000
σ = 1.0
a = numpy.matrix([[1.0, 2.0, 1.0],
                  [4.0, 1.0, -2.0],
                  [-2.0, 1.0, 5.0]])
x, y = multivariate_test_sample(a, n, σ)
simple_multivariate_ols(x, y)

# %%

result = LinearRegression().fit(x.T, y.T)
result.coef_

# %%

df = samples_to_data_frame(numpy.concatenate((y[0], x)))
result = multiple_ols(df, "x1 ~ x2 + x3 + x4")
print(result.summary())

df = samples_to_data_frame(numpy.concatenate((y[1], x)))
result = multiple_ols(df, "x1 ~ x2 + x3 + x4")
print(result.summary())

df = samples_to_data_frame(numpy.concatenate((y[2], x)))
result = multiple_ols(df, "x1 ~ x2 + x3 + x4")
print(result.summary())

# %%
# Test one cointegration vector with one cointegration vector

nsample = 1000
α = numpy.matrix([-0.5, 0.0, 0.0]).T
β = numpy.matrix([1.0, -0.5, -0.5])
a = numpy.matrix([[0.5, 0.0, 0.0],
                  [0.0, 0.5, 0.0],
                  [0.0, 0.0, 0.5]])
Ω = numpy.matrix([[1.0, 0.0, 0.0],
                  [0.0, 1.0, 0.0],
                  [0.0, 0.0, 1.0]])

title = "Trivariate VECM 1 Cointegrating Vector"
labels = [r"$x_1$", r"$x_2$", r"$x_3$"]
plot = "vecm_analysis_samples"
df = vecm_generate_sample(α, β, a, Ω, nsample)

# %%

comparison_plot(title, df, α.T, β, labels, [0.1, 0.1], plot)

# %%

johansen_coint_theory(df)

# %%

johansen_coint(df)

# %%

result = multiple_ols(df, "x1 ~ x2 + x3")
print(result.summary())

# %%

sample_adf_test(df)

# %%

residual_adf_test(df, result.params)

# %%

title = "Trivariate VECM 1 Cointegrating Vector First Difference"
labels = [r"$Δx_1$", r"$Δx_2$", r"$Δx_3$"]
plot = "vecm_analysis_samples_diff_1"
df_diff_1 = difference(df)
comparison_plot(title, df_diff_1, α.T, β, labels, [0.1, 0.8], plot)

# %%

sample_adf_test(df_diff_1)

# %%

result = VAR(df_diff_1).select_order(maxlags=15)
result.ics
result.selected_orders

# %%

result = VECM(df, k_ar_diff=12, coint_rank=1, deterministic="nc").fit()
result.coint_rank
result.alpha
result.beta
result.gamma