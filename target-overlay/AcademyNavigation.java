package org.sasanlabs.academy;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/** Entry routes for the educational overlay; upstream vulnerability routes stay intact. */
@Controller
public class AcademyNavigation {
    @GetMapping({"/mercado", "/mercado/"})
    public String market() {
        return "forward:/mercado/index.html";
    }

    @GetMapping({"/original", "/original/"})
    public String original() {
        return "forward:/original/index.html";
    }
}
