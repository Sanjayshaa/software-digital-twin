package com.example;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PaymentService {
    @PostMapping("/charges")
    public String charge() {
        return "charged";
    }
}
