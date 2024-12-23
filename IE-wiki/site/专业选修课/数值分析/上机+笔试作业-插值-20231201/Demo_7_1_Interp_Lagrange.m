%
% Lagrange 插值
%   --- 线性插值和抛物线插值, 计算 ln(5.4)
%
clear; clc;

X = 0.4 : 0.1 : 0.8;
Y = [-0.9163, -0.6931, -0.5108, -0.3567, -0.2231];
x = 0.54; % 需要插值的点

% 线性插值
x0 = X(2); y0 = Y(2);
x1 = X(3); y1 = Y(3);
y = y0*(x-x1)/(x0-x1) + y1*(x-x0)/(x1-x0);
fprintf('线性插值的结果为：%.4f, err=%.2e\n', y, abs(y-log(0.54)))

% 抛物线插值
x0 = X(2); y0 = Y(2);
x1 = X(3); y1 = Y(3);
x2 = X(1); y2 = Y(1);
y = y0*(x-x1)*(x-x2)/((x0-x1)*(x0-x2)) + ...
    y1*(x-x0)*(x-x2)/((x1-x0)*(x1-x2)) + ...
    y2*(x-x0)*(x-x1)/((x2-x0)*(x2-x1));
fprintf('抛物线插值的结果为：%.4f, err=%.2e\n', y, abs(y-log(0.54)))

% n 次插值
n = length(X) - 1;
y = 0;
for k = 0 : n
    y = y + Y(k+1)*prod(x-X([1:k,k+2:end]))/prod(X(k+1)-X([1:k,k+2:end]));
end
fprintf('%d次插值的结果为：%.4f, err=%.2e\n', n, y, abs(y-log(0.54)))


