import torch 
from math import pi, log 

log_max = log(1e4)
log_min = log(1e-8)

def loss_fn(inp, out_dehaze, out_transmission, gt_dehaze, gt_transmission, A, sigma, eps1, eps2):
    '''
    Input: 
        eps1 : variance for prior of Z (epsilon^2를 기본으로 줄 것임)
        eps2 : variance for prior of T 
        sigma : variance of y 
    '''
    
    # out_dehaze, out_transmission = torch.clamp(out_dehaze, min=0, max=1), torch.clamp(out_transmission, min=0, max=1)
    
    # parameters predicted of dehaze 
    alpha = out_dehaze[:, :3]
    m2 = torch.exp(out_dehaze[:,3:].clamp_(min=log_min, max= log_max))

    # parameters predicted of transmission
    beta = out_transmission[:, :1]
    n2 = torch.exp(out_transmission[:, 1:].clamp_(min=log_min, max=log_max))

    # KL divergence for dehaze 
    m2_div_eps1 = torch.div(m2, eps1)
    kl_dehaze = 0.5 * torch.mean(-torch.log(m2_div_eps1) -1 + m2_div_eps1 + ((alpha-gt_dehaze)**2 / eps1))
    # kl_dehaze = 0.5 * torch.mean(m2  + (alpha-gt_dehaze)**2)

    # KL divergence for transmission 
    n2_div_eps2 = torch.div(n2, eps2)
    kl_transmission = 0.5 * torch.mean(-torch.log(n2_div_eps2) -1 + n2_div_eps2 + ((beta-gt_transmission)**2 / eps2))    
    # kl_transmission = 0.5 * torch.mean(n2  + (beta-gt_transmission)**2)

    # Likelihood
    lh = 0.5 * torch.log(torch.tensor(2*pi)) + 0.5* torch.log(torch.tensor(sigma)) + 0.5 * torch.mean(((inp - (alpha*beta) - A*(1-beta))**2)/sigma + 1)
    # sigma = eps1*eps2 + gt_transmission**2*eps1 + (gt_dehaze**2+A**2)*eps2
    # lh = 0.5 * torch.log(torch.tensor(2*pi)) + 0.5* torch.log(torch.mean(sigma)) + 0.5 * torch.mean(torch.div((inp - (alpha*beta) - A*(1-beta))**2,sigma) + 1)
    # lh = 0.5 * torch.mean(((inp - (alpha*beta) + A*(1-beta))**2))
    
    total_loss = kl_transmission + kl_dehaze + lh

    return total_loss, lh, kl_dehaze, kl_transmission

def laplace_loss(inp, out_dehaze, out_transmission, gt_dehaze, gt_transmission, A, sigma, eps1, eps2):
    '''
    Info: 
        laplace에서는 epsilon을 제곱하지 않은 값으로 입력값을 받음 
        J ~ Laplace(gt_dehaze, eps1), E(J) = gt_dehaze, Var(J) = 2*eps1**2
        T ~ Laplace(gt_transmission, eps2), E(T) = gt_transmission, Var(T) = 2*eps2**2
    '''
    
    # out_dehaze, out_transmission = torch.clamp(out_dehaze, min=0, max=1), torch.clamp(out_transmission, min=0, max=1)
    
    # parameters predicted of dehaze 
    alpha = out_dehaze[:, :3]
    m2 = torch.exp(out_dehaze[:,3:].clamp_(min=log_min, max= log_max))

    # parameters predicted of transmission
    beta = out_transmission[:, :1]
    n2 = torch.exp(out_transmission[:, 1:].clamp_(min=log_min, max=log_max))

    # KL divergence for dehaze 
    m2_div_eps1 = torch.div(m2, eps1)
    kl_dehaze = torch.mean(m2_div_eps1 + torch.exp(-torch.abs(alpha-gt_dehaze)/eps1) + torch.abs(alpha-gt_dehaze)/eps1 - torch.log(m2_div_eps1) -1)
    
    # KL divergence for transmission 
    n2_div_eps2 = torch.div(n2, eps2)
    kl_transmission = torch.mean(n2_div_eps2 + torch.exp(-torch.abs(beta-gt_transmission)/eps2) + torch.abs(beta-gt_transmission)/eps2 - torch.log(n2_div_eps2) -1)    
    
    # Likelihood
    # sigma = eps1*eps2 + out_transmission**2*eps1 + (gt_dehaze**2+A**2)*eps2
    eps1, eps2 = 2*eps1**2, 2*eps2**2
    sigma = eps1*eps2 + gt_transmission**2*eps1 + gt_dehaze**2*eps2 + A**2*gt_transmission**2 - 2*A*gt_dehaze*eps2
    lh = 0.5 * torch.log(torch.tensor(2*pi)) + 0.5* torch.mean(torch.log(torch.tensor(sigma))) + 0.5 * torch.mean(((inp - (alpha*beta) - A*(1-beta))**2)/sigma + 1)
    # lh = 0.5 * torch.log(torch.tensor(2*pi)) + 0.5* torch.log(torch.tensor(sigma)) + 0.5 * torch.mean(((inp - (alpha*beta) - A*(1-beta))**2)/sigma + 1)
    
    total_loss = kl_transmission + kl_dehaze + lh

    return total_loss, lh, kl_dehaze, kl_transmission
