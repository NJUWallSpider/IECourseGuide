%
% ��ֵ�����ʾ: Runge ����
%
clear; clc;

f = @(x) 1./(1+x.^2);
a = -5; 
b = 5;

xi = -5: 0.01 :5;  % ���ڻ�ͼ�ĵȾ���ɢ��
yt = f(xi);  % ��������Щ���ϵľ�ȷֵ

for n = 2  : 2 : 12
    % n = 5;
    X = [ a : (b-a)/n : b ];  % ��ֵ�ڵ�
    Y = f(X);
    
    yi = zeros(1,length(xi));  % �洢ͨ����ֵ����Ľ���ֵ
    for i = 1 : length(xi)
        for k = 0 : n
	    xtmp1 = xi(i)-X([1:k,k+2:end]);
	    xtmp2 = X(k+1)-X([1:k,k+2:end]);
            yi(i) = yi(i) + Y(k+1)*prod(xtmp1./xtmp2);
        end
    end
    
    plot(xi,yt,'r-', xi,yi,'b-','LineWidth',2);
    hold on;
    plot(X,Y,'bo','LineWidth',2,'markersize',10);
    hold off;
    axis([-5,5,-4,2]);
    tit = ['n=',int2str(n)];
    title(tit,'FontSize',20); 
    legend({'f(x)','L_n(x)'},'FontSize',20,'FontName', 'Times New Roman','FontAngle','italic')
    shg
    pause 
end
