% 
% Steffenson 迭代
%

clear all; 
close all;

f = @(x) x^3-x-1;
g = @(x) x^3-1;

fprintf('True solution: x = %.8f\n',fzero(f,[1,2])) %非线性函数在[1,2]的根

n = 6; % 设置迭代步数
x = 1.5; % 迭代初始值

% 不动点迭代
fprintf('普通不动点迭代\n')
for k = 1 : n
    x = g(x);
    fprintf('k=%d, x=%.8g\n',k,x);
end
   
% Steffenson 迭代
x = 1.5; % 迭代初始值
fprintf('===================\n');
fprintf('Steffenson 迭代\n');
for k = 1 : n
    x1 = g(x); x2 = g(x1);
    x = x - (x1-x)^2/(x2-2*x1+x);
    fprintf('k=%d, x=%.8f\n',k,x);
end