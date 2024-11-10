%
% 不动点迭代
%
clear all;
close all;

f = @(x) x^3-x-1;      % 原函数
g = @(x) (x+1)^(1/3);  % 迭代函数 
maxit = 10;            % 最大迭代步数

fprintf('迭代函数: g=%s\n', char(g));

fvalue = zeros(maxit,1);

x = 1.5; % 取中点为迭代初始值
for k = 1 : maxit
    x = g(x);
    fvalue(k) = abs(f(x));
    fprintf('k=%d, x=%.4f, f(x)=%.2e\n',k, x, fvalue(k));
end

% 绘图：函数值下降曲线
semilogy(1:maxit, fvalue, 'ob-')
xlabel('k'); ylabel('|f(x)|');
title('函数值下降曲线')