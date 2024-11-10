%
% Demo for computing ln(2)
%

clear;

fprintf('精确值：ln(2)~%.20f\n',log(2));

% 方法一：ln(1+x) 的 Taylor 展开
disp('方法一：')
x = 1.0;
s = 0.0;
xtmp = -1;
for k = 1 : 100
    xtmp = -xtmp*x;
    s = s + xtmp/k;
    fprintf('k=%d, s=%.8f, err=%.1e\n', k, s, abs(s-log(2)));
end



% 方法二：ln((1+x)/(1-x)) 的 Taylor 展开
disp('方法二：')
x = 1.0/3;
s = 2*x;
xtmp = x;
fprintf('k=1, s=%.8f, err=%.1e\n', s, abs(s-log(2)));
for k = 2 : 10
    xtmp = xtmp*x*x;
    s = s + 2*xtmp/(2*k-1);
    fprintf('k=%d, s=%.8f, err=%.1e\n', k, s, abs(s-log(2)));
end

