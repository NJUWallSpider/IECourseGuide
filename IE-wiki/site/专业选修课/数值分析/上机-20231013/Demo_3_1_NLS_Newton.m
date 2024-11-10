%
% Newton 法
%
clear all; 
close all;

f = @(x) x*exp(x)-1;
df = @(x) exp(x)*(1+x);  %syms x; diff(x*exp(x)-1)用于求偏导数

n = 10;
tol = 1e-6;
x0 = 0.5; % 迭代初始值
fprintf('x0=%.8f, f(x)=%.2e\n', x0, f(x0));
for k = 1 : n
    x = x0 - f(x0)/df(x0);
    fprintf('k=%d, x=%.8f, f(x)=%.2e\n', k, x, f(x));
    if abs(x-x0)<tol, break, end
    x0 = x;
end

